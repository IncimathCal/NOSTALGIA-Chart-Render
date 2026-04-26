"""
NOSTALGIA 谱面渲染器

使用 Pillow 将 Chart 对象渲染为 PNG 图像。
"""

from __future__ import annotations
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw

from .element import Chart, Note
from .rhythm import analyze_chart_rhythm
from .texture_loader import get_loader
from .theme import DEFAULT_THEME, Theme, load_font


SCREEN_MIN_KEY = 1
SCREEN_MAX_KEY = 28


class Coordinate:
    """坐标转换"""

    def __init__(self, theme: Theme, chart: Chart):
        self.theme = theme
        self.chart = chart
        self.track_left = theme.margin_left
        self.track_right = theme.margin_left + theme.track_width
        self.key_width = theme.key_width

        self.time_height = chart.finish_time_ms / theme.resize
        self.canvas_height = int(self.time_height + theme.track_reserved_top + theme.track_reserved_bottom)
        self.canvas_width = theme.margin_left + theme.track_width + theme.margin_right
        self.judge_line_y = self.canvas_height - theme.track_reserved_bottom - theme.judge_line_offset

    def key_to_x(self, key_index: float) -> int:
        return round(self.track_left + (key_index - SCREEN_MIN_KEY) * self.key_width)

    def time_to_y(self, time_ms: int) -> int:
        return round(self.canvas_height - self.theme.track_reserved_bottom - time_ms / self.theme.resize)

    def note_rect(self, note: Note) -> Tuple[int, int, int, int]:
        base_width = round(self.theme.key_width * (note.key_width + 1))
        total_width = round(base_width * 1.3)
        center_x = self.key_to_x(note.center_key + 0.5)
        left = center_x - total_width // 2
        right = center_x + total_width // 2
        bottom = self.time_to_y(note.start_ms) + 7

        if note.note_type in (2, 10, 64):
            top = self.time_to_y(note.end_ms) + 7
        else:
            top = bottom - self.theme.note_height

        return left, top, right, bottom


class Renderer:
    """NOSTALGIA 谱面渲染器"""

    def __init__(
        self,
        chart: Chart,
        theme: Optional[Theme] = None,
        song_title: str = "",
        artist: str = "",
        difficulty: str = "",
        cover_path: Optional[str] = None,
        level: str = "",
    ):
        self.chart = chart
        self.theme = theme or DEFAULT_THEME
        self.song_title = song_title
        self.artist = artist
        self.difficulty = difficulty
        self.cover_path = cover_path
        self.level = level

        self.coord = Coordinate(self.theme, chart)
        self.im: Optional[Image.Image] = None
        self.draw: Optional[ImageDraw.ImageDraw] = None

        self._render()

    def _render(self):
        self.im = Image.new("RGBA", (self.coord.canvas_width, self.coord.canvas_height), self.theme.track_bg)
        self.draw = ImageDraw.Draw(self.im)

        self._draw_track_background()
        self._draw_beat_lines()
        self._draw_key_separators()
        self._draw_variable_speed_layer()
        self._draw_glissando_chain_connections()
        self._draw_notes()
        self._draw_judge_line()
        self._post_process_segment()
        self._draw_segment_annotations()
        self._add_header()
        self._draw_combo_milestones()
        self._draw_footer()

    # ------------------------------------------------------------------
    # 轨道背景
    # ------------------------------------------------------------------

    def _draw_track_background(self):
        top = self.theme.track_reserved_top
        bottom = self.coord.canvas_height - self.theme.track_reserved_bottom
        for k in range(SCREEN_MIN_KEY, SCREEN_MAX_KEY + 1):
            x1 = self.coord.key_to_x(k)
            x2 = self.coord.key_to_x(k + 1)
            color = self.theme.track_bg_alt if self._is_black_key(k) else self.theme.track_bg
            self.draw.rectangle([x1, top, x2, bottom], fill=color)

    @staticmethod
    def _is_black_key(key_index: int) -> bool:
        return (key_index - 3) % 12 in (1, 4, 6, 9, 11)

    # ------------------------------------------------------------------
    # 拍子线
    # ------------------------------------------------------------------

    def _draw_beat_lines(self):
        if not self.chart.timing_list:
            return
        for i, timing in enumerate(self.chart.timing_list):
            end_ms = self.chart.timing_list[i + 1].time_ms if i + 1 < len(self.chart.timing_list) else self.chart.end_time
            if timing.bpm <= 0:
                continue
            beat_ms = 60000 / timing.bpm
            t = timing.time_ms
            while t < end_ms:
                y = self.coord.time_to_y(int(t))
                if self.theme.track_reserved_top <= y <= self.coord.canvas_height - self.theme.track_reserved_bottom:
                    self.draw.line(
                        [(self.coord.track_left, y), (self.coord.track_right, y)],
                        fill=self.theme.beat_line,
                        width=self.theme.beat_line_width,
                    )
                t += beat_ms

    # ------------------------------------------------------------------
    # 琴键分隔线
    # ------------------------------------------------------------------

    def _draw_key_separators(self):
        top = self.theme.track_reserved_top
        bottom = self.coord.canvas_height - self.theme.track_reserved_bottom
        for k in range(SCREEN_MIN_KEY, SCREEN_MAX_KEY + 2):
            x = self.coord.key_to_x(k)
            self.draw.line([(x, top), (x, bottom)], fill=self.theme.track_split_line, width=1)

    # ------------------------------------------------------------------
    # 变速区域
    # ------------------------------------------------------------------

    def _draw_variable_speed_layer(self):
        base_bpm = self.chart.first_bpm
        if not self.chart.timing_list:
            return

        overlay = Image.new("RGBA", self.im.size, self.theme.transparent)
        overlay_draw = ImageDraw.Draw(overlay)

        for i, timing in enumerate(self.chart.timing_list):
            if abs(timing.bpm - base_bpm) < 0.1:
                continue
            end_ms = self.chart.timing_list[i + 1].time_ms if i + 1 < len(self.chart.timing_list) else self.chart.end_time
            y1 = self.coord.time_to_y(timing.time_ms)
            y2 = self.coord.time_to_y(end_ms)
            top_y, bottom_y = min(y1, y2), max(y1, y2)
            overlay_draw.rectangle(
                [self.coord.track_left, top_y, self.coord.track_right, bottom_y],
                fill=self.theme.variable_speed_layer,
            )

        self.im.alpha_composite(overlay)

    # ------------------------------------------------------------------
    # Note 渲染
    # ------------------------------------------------------------------

    def _draw_notes(self):
        for note in self.chart.note_list:
            if note.hand == 2:
                continue
            self._draw_note(note)

    def _draw_note(self, note: Note):
        left, top, right, bottom = self.coord.note_rect(note)
        color = self.theme.note_colors.get(note.note_type, self.theme.note_colors[0])

        if bottom - top < self.theme.note_height:
            bottom = top + self.theme.note_height

        if note.note_type == 2:
            self._draw_long(note, left, top, right, bottom)
        elif note.note_type == 10:
            self._draw_long(note, left, top, right, bottom)
        elif note.note_type == 64:
            self._draw_trill(note, left, top, right, bottom)
        elif note.note_type in (4, 12):  # Glissando / Chain (游戏中相同)
            if not self._draw_textured(note, left, top, right, bottom):
                self._fallback_glissando(note, left, top, right, bottom, color)
        elif note.note_type == 8:
            if not self._draw_textured(note, left, top, right, bottom, override_type=0):
                self._fallback_normal(note, left, top, right, bottom, color)
        else:
            if not self._draw_textured(note, left, top, right, bottom):
                self._fallback_normal(note, left, top, right, bottom, color)

    def _draw_textured(self, note: Note, left: int, top: int, right: int, bottom: int, override_type: int = None) -> bool:
        w = right - left
        h = bottom - top
        if w <= 0 or h <= 0:
            return False

        note_type = override_type if override_type is not None else note.note_type
        # Chain (type 12) 在游戏中和 Glissando (type 4) 相同，使用 glissando 纹理
        if note_type == 12:
            note_type = 4
        tex = get_loader().get_texture(note_type, note.key_width, note.center_key, note.hand)
        if tex is None:
            return False

        tex = tex.resize((w, h), Image.LANCZOS)
        self.im.alpha_composite(tex, (left, top))

        if note.note_type in (4, 12) and (note.is_glissando_head() or note.is_glissando_tail()):
            self._glissando_arrows(note, left, top, right, bottom)

        return True

    # -- Long-like notes (2, 10, 64) -----------------------------------

    def _draw_long(self, note: Note, left: int, top: int, right: int, bottom: int):
        # hand=1 左手(蓝), hand=0 右手(红)
        self._draw_sustained(note, left, top, right, bottom,
                             mid_color=(80, 160, 255, 128) if note.hand == 1 else (255, 80, 80, 128),
                             head_type=0)

    def _draw_special(self, note: Note, left: int, top: int, right: int, bottom: int):
        self._draw_sustained(note, left, top, right, bottom,
                             mid_color=(255, 200, 80, 128),
                             head_type=10)

    def _draw_trill(self, note: Note, left: int, top: int, right: int, bottom: int):
        self._draw_sustained(note, left, top, right, bottom,
                             mid_color=(255, 220, 60, 128),
                             head_type=64,
                             use_trill_piano_head=True)

    def _draw_sustained(self, note: Note, left: int, top: int, right: int, bottom: int,
                        mid_color: tuple, head_type: int,
                        use_trill_piano_head: bool = False):
        total_width = right - left
        center_x = (left + right) // 2
        head_h = self.theme.note_height
        head_w = total_width
        head_left = center_x - head_w // 2

        # 根据头尾纹理的实际内容占比调整中间条宽度，再缩至80%
        if use_trill_piano_head:
            content_ratio = get_loader().get_trill_piano_ratio(note.key_width, note.hand)
        else:
            content_ratio = get_loader().get_content_ratio(head_type, note.key_width, note.center_key, note.hand)
        mid_width = max(int(total_width * content_ratio * 0.8), 4)  # 最小4px防止太细
        mid_left = center_x - mid_width // 2
        mid_right = center_x + mid_width // 2
        mid_top = top + head_h // 2
        mid_bottom = bottom - head_h // 2

        if mid_bottom > mid_top:
            if use_trill_piano_head:
                self._draw_trill_layers(mid_left, mid_top, mid_right, mid_bottom, note.hand, head_h)
            else:
                overlay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
                ImageDraw.Draw(overlay).rectangle([mid_left, mid_top, mid_right, mid_bottom], fill=mid_color)
                self.im.alpha_composite(overlay)

        # 头部纹理
        if use_trill_piano_head:
            head_tex = get_loader().get_trill_piano(note.key_width, note.hand)
        else:
            head_tex = get_loader().get_texture(head_type, note.key_width, note.center_key, note.hand)

        # 尾部纹理：long_end（trill 和 long 统一）
        tail_tex = get_loader().get_long_end(note.key_width, note.hand)

        if head_tex:
            head_tex = head_tex.resize((head_w, head_h), Image.LANCZOS)
            self.im.alpha_composite(head_tex, (head_left, bottom - head_h))
        else:
            c = self.theme.note_colors.get(head_type, (100, 180, 255, 230))
            self.draw.rectangle([head_left, bottom - head_h, head_left + head_w, bottom], fill=c)

        if tail_tex:
            tail_tex = tail_tex.resize((head_w, head_h), Image.LANCZOS)
            self.im.alpha_composite(tail_tex, (head_left, top))
        else:
            c = self.theme.note_colors.get(head_type, (100, 180, 255, 230))
            self.draw.rectangle([head_left, top, head_left + head_w, top + head_h], fill=c)

    # -- Fallbacks ------------------------------------------------------

    def _fallback_normal(self, note: Note, left: int, top: int, right: int, bottom: int, color: tuple):
        self.draw.rectangle([left, top, right, bottom], fill=color)
        self.draw.rectangle([left, top, right, bottom], outline=(*color[:3], 255), width=1)

    def _fallback_glissando(self, note: Note, left: int, top: int, right: int, bottom: int, color: tuple):
        self.draw.rectangle([left, top, right, bottom], fill=color)
        self._glissando_arrows(note, left, top, right, bottom)

    def _fallback_chain(self, note: Note, left: int, top: int, right: int, bottom: int, color: tuple):
        self.draw.rectangle([left, top, right, bottom], fill=color)
        self._chain_dashes(left, top, right, bottom)

    # -- Decorations ----------------------------------------------------

    def _glissando_arrows(self, note: Note, left: int, top: int, right: int, bottom: int):
        c = (255, 255, 255, 200)
        if note.is_glissando_head():
            x = left + 4
            self.draw.polygon([(x, top + 2), (x + 8, (top + bottom) // 2), (x, bottom - 2)], fill=c)
        if note.is_glissando_tail():
            x = right - 4
            self.draw.polygon([(x, top + 2), (x - 8, (top + bottom) // 2), (x, bottom - 2)], fill=c)

    def _draw_trill_layers(self, mid_left: int, mid_top: int, mid_right: int, mid_bottom: int,
                           hand: int, head_h: int):
        """
        Trill 中间条：交替渐变层。
        每层厚度 = head_h / 2。
        奇数层：左→右，左边红/蓝，右边透明。
        偶数层：右→左，右边红/蓝，左边透明。
        渐变中心偏右（用幂函数 p=2），整体再叠 50% 不透明度（同 hold）。
        """
        import numpy as np

        total_width = mid_right - mid_left
        total_height = mid_bottom - mid_top
        layer_h = max(1, head_h // 2)
        if total_width <= 0 or total_height <= 0:
            return

        base_color = (80, 160, 255) if hand == 1 else (255, 80, 80)
        num_layers = (total_height + layer_h - 1) // layer_h

        overlay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))

        for i in range(num_layers):
            y1 = mid_top + i * layer_h
            y2 = min(y1 + layer_h, mid_bottom)
            h = y2 - y1
            if h <= 0:
                continue

            # 水平 alpha mask，整体再乘 0.5（hold 同等级 50% 不透明度）
            xs = np.linspace(0.0, 1.0, total_width)
            if i % 2 == 0:
                # 第一层（i=0）：左边有色，右边透明；渐变中心偏右
                alphas = (255 * (1.0 - xs ** 2) * 0.8).astype(np.uint8)
            else:
                # 第二层：右边有色，左边透明；渐变中心偏左（镜像）
                alphas = (255 * (1.0 - (1.0 - xs) ** 2) * 0.8).astype(np.uint8)

            # 构建 RGBA layer
            layer = np.zeros((h, total_width, 4), dtype=np.uint8)
            layer[:, :, 0] = base_color[0]
            layer[:, :, 1] = base_color[1]
            layer[:, :, 2] = base_color[2]
            layer[:, :, 3] = alphas

            layer_img = Image.fromarray(layer, "RGBA")
            overlay.paste(layer_img, (mid_left, y1), layer_img)

        self.im.alpha_composite(overlay)

    def _trill_waves(self, left: int, top: int, right: int, bottom: int):
        c = (255, 255, 255, 150)
        mid_y = (top + bottom) // 2
        width = right - left
        for i in range(0, width, 8):
            x1 = left + i
            x2 = left + min(i + 4, width)
            self.draw.line([(x1, mid_y - 3), (x2, mid_y + 3)], fill=c, width=1)
            if i + 4 < width:
                x3 = left + min(i + 8, width)
                self.draw.line([(x2, mid_y + 3), (x3, mid_y - 3)], fill=c, width=1)

    def _chain_dashes(self, left: int, top: int, right: int, bottom: int):
        c = (255, 255, 255, 200)
        for x in range(left, right, 6):
            self.draw.line([(x, top), (min(x + 3, right), top)], fill=c, width=1)
        for x in range(left, right, 6):
            self.draw.line([(x, bottom), (min(x + 3, right), bottom)], fill=c, width=1)

    # ------------------------------------------------------------------
    # Glissando 链连接线（独立模块，便于随时修改/移除）
    # ------------------------------------------------------------------

    def _draw_glissando_chain_connections(self):
        """
        绘制 Glissando 链中相邻 note 的连接平行四边形。
        以链中每个 note 的宽度为宽，连接 n_i 顶部与 n_{i+1} 底部，
        hand=1 左手半透明蓝，hand=0 右手半透明红。
        """
        chains = self.chart.get_glissando_chains()
        if not chains:
            return

        overlay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        for chain in chains:
            for i in range(len(chain) - 1):
                n1 = chain[i]
                n2 = chain[i + 1]

                left1, top1, right1, bottom1 = self.coord.note_rect(n1)
                left2, top2, right2, bottom2 = self.coord.note_rect(n2)

                # 确保最小高度
                if bottom1 - top1 < self.theme.note_height:
                    top1 = bottom1 - self.theme.note_height
                if bottom2 - top2 < self.theme.note_height:
                    top2 = bottom2 - self.theme.note_height

                # 平行四边形：以 note 中心为上下边缘，宽度缩减至 30%
                cy1 = (top1 + bottom1) // 2
                cy2 = (top2 + bottom2) // 2
                w1 = right1 - left1
                w2 = right2 - left2
                shrink1 = int(w1 * 0.25)
                shrink2 = int(w2 * 0.25)
                nl1, nr1 = left1 + shrink1, right1 - shrink1
                nl2, nr2 = left2 + shrink2, right2 - shrink2
                poly = [(nl1, cy1), (nr1, cy1), (nr2, cy2), (nl2, cy2)]

                # hand=1 左手蓝，hand=0 右手红
                color = (80, 160, 255, 110) if n1.hand == 1 else (255, 80, 80, 110)
                overlay_draw.polygon(poly, fill=color)

        self.im.alpha_composite(overlay)

    # ------------------------------------------------------------------
    # 判定线
    # ------------------------------------------------------------------

    def _draw_judge_line(self):
        y = self.coord.time_to_y(0)
        self.draw.line([(self.coord.track_left, y), (self.coord.track_right, y)], fill=self.theme.judge_line, width=3)
        self.draw.text((self.coord.track_right + 10, y), "JUDGE",
                       font=self.theme.font_small, fill=self.theme.judge_line, anchor="lm")

    # ------------------------------------------------------------------
    # 分段后注释（避免被裁剪）
    # ------------------------------------------------------------------

    def _segment_time_to_y(self, time_ms: int, segment_start_ms: int) -> int:
        return round(self.coord.canvas_height - self.theme.track_reserved_bottom - (time_ms - segment_start_ms) / self.theme.resize)

    def _draw_segment_annotations(self):
        if not getattr(self, "_segments", None):
            return

        orig_w = self.theme.margin_left + self.theme.track_width + self.theme.margin_right

        for i, (start_ms, end_ms, _) in enumerate(self._segments):
            col_x = i * orig_w
            track_left = col_x + self.theme.margin_left
            track_right = col_x + self.theme.margin_left + self.theme.track_width

            # BPM 注释
            for timing in self.chart.timing_list:
                if not (start_ms <= timing.time_ms <= end_ms):
                    continue
                y = self._segment_time_to_y(timing.time_ms, start_ms)
                if y < self.theme.track_reserved_top or y > self.coord.canvas_height - self.theme.track_reserved_bottom:
                    continue
                self.draw.text((track_left - 8, y), f"{timing.bpm:.1f}",
                               font=self.theme.font_bpm, fill=self.theme.text_bpm, anchor="rm")

            # 节奏注释
            for beat in analyze_chart_rhythm(self.chart):
                if not (start_ms <= beat.time_ms <= end_ms):
                    continue
                text = beat.format()
                if not text:
                    continue
                y = self._segment_time_to_y(beat.time_ms, start_ms)
                if y < self.theme.track_reserved_top or y > self.coord.canvas_height - self.theme.track_reserved_bottom:
                    continue
                self.draw.text((track_right + 8, y), text,
                               font=self.theme.font_bar_beat, fill=self.theme.text_bar_beat, anchor="lm")

    # ------------------------------------------------------------------
    # 分段平铺
    # ------------------------------------------------------------------

    def _calculate_segments(self) -> list[tuple[int, int, int]]:
        """返回 (start_ms, end_ms, display_end_ms) 列表。end_ms 为实际结束时间（不含重叠）。"""
        if self.chart.end_time <= 25000:
            return [(0, self.chart.end_time, self.chart.end_time)]

        TARGET = 20000
        MIN_SEG = 10000
        OVERLAP = 50
        segments = []
        start = 0

        while start < self.chart.end_time:
            bpm = self.chart.get_bpm_at(start) or self.chart.first_bpm
            bar = 4 * 60000 / bpm
            bars = max(1, int(TARGET / bar))
            end = start + bars * bar
            while end - start < MIN_SEG and end < self.chart.end_time:
                bars += 1
                end = start + bars * bar
            if end > self.chart.end_time:
                end = self.chart.end_time
            display_end = min(end + OVERLAP, self.chart.end_time) if end < self.chart.end_time else end
            segments.append((int(start), int(end), int(display_end)))
            start = end

        return segments

    def _post_process_segment(self):
        raw_segments = self._calculate_segments()
        self._segments = raw_segments

        if len(raw_segments) <= 1:
            return

        orig_w, orig_h = self.im.size
        boxes = []
        for s, e, de in raw_segments:
            y1, y2 = sorted([self.coord.time_to_y(de), self.coord.time_to_y(s)])
            y2 = min(y2 + 2, orig_h)
            boxes.append((0, y1, orig_w, y2))

        max_h = max(y2 - y1 for _, y1, _, y2 in boxes)
        new_w = len(raw_segments) * orig_w
        new_h = max_h + self.theme.track_reserved_top + self.theme.track_reserved_bottom

        new_im = Image.new("RGBA", (new_w, new_h), self.theme.track_bg)
        for i, box in enumerate(boxes):
            seg = self.im.crop(box)
            new_im.paste(seg, (i * orig_w, new_h - seg.height - self.theme.track_reserved_bottom))

        self.im = new_im
        self.draw = ImageDraw.Draw(self.im)
        self.coord.canvas_width = new_w
        self.coord.canvas_height = new_h

    # ------------------------------------------------------------------
    # 顶部信息栏（Header）
    # ------------------------------------------------------------------

    def _add_header(self):
        header_h = 220

        new_w = self.im.width
        new_h = self.im.height + header_h
        new_im = Image.new("RGBA", (new_w, new_h), self.theme.track_bg)

        new_im.paste(self.im, (0, header_h))

        self.im = new_im
        self.draw = ImageDraw.Draw(self.im)
        self.coord.canvas_height += header_h

        self._draw_header_content(header_h)

    def _draw_header_content(self, header_h: int):
        padding = 30
        cover_size = 160

        cover_x = padding
        cover_y = (header_h - cover_size) // 2

        if self.cover_path and os.path.exists(self.cover_path):
            try:
                cover = Image.open(self.cover_path).convert("RGBA").resize((cover_size, cover_size))
                self.im.alpha_composite(cover, (cover_x, cover_y))
                text_x = cover_x + cover_size + 24
            except Exception:
                text_x = cover_x
        else:
            text_x = cover_x

        font_title = load_font(53)
        font_artist = load_font(33)
        font_diff = load_font(28)

        self.draw.text((text_x, cover_y + 25), self.song_title,
                       font=font_title, fill=self.theme.text_title, anchor="lm")
        self.draw.text((text_x, cover_y + 70), self.artist,
                       font=font_artist, fill=self.theme.text_subtitle, anchor="lm")

        diff = "Expert" if self.difficulty == "Extreme" else self.difficulty
        display_level = self.level
        if diff == "Real" and display_level.isdigit():
            display_level = str(int(display_level) - 10)
        level_str = f" {display_level}" if display_level else ""
        self.draw.text((text_x, cover_y + 110), f"Difficulty: {diff}{level_str}",
                       font=font_diff, fill=self.theme.text_subtitle, anchor="lm")

        # 统计信息（右侧偏左）逐行绘制，字体放大
        stats = self._get_statistics_text().splitlines()
        stats_x = self.im.width - padding - 340
        line_height = 28
        font_stats_large = load_font(26)
        for idx, line in enumerate(stats):
            self.draw.text((stats_x, cover_y + 15 + idx * line_height), line,
                           font=font_stats_large, fill=self.theme.text_stats)

    def _get_statistics_text(self) -> str:
        lines = []
        lines.append(f"Duration: {self.chart.end_time / 1000:.1f}s")

        bpms = [t.bpm for t in self.chart.timing_list if t.bpm > 0]
        if bpms:
            bpm_text = f"BPM: {min(bpms):.1f}" if abs(max(bpms) - min(bpms)) < 0.5 else f"BPM: {min(bpms):.1f}~{max(bpms):.1f}"
        else:
            bpm_text = "BPM: --"
        lines.append(bpm_text)

        counts: dict[str, int] = {}
        for n in self.chart.note_list:
            if n.hand == 2:
                continue
            name = self._note_type_name(n.note_type)
            counts[name] = counts.get(name, 0) + 1

        total = 0
        for name in ["Normal", "Long", "Glissando", "Trill"]:
            if name in counts:
                lines.append(f"{name}: {counts[name]}")
                total += counts[name]
        lines.append(f"Total: {total}")

        return "\n".join(lines)

    @staticmethod
    def _note_type_name(note_type: int) -> str:
        if note_type in (0, 8):
            return "Normal"
        if note_type in (2, 10):
            return "Long"
        if note_type in (4, 12):
            return "Glissando"
        if note_type == 64:
            return "Trill"
        return "Unknown"

    # ------------------------------------------------------------------
    # 右下角生成器信息
    # ------------------------------------------------------------------

    def _draw_footer(self):
        font_large = load_font(24)
        right_x = self.im.width - self.theme.margin_right
        bottom_y = self.im.height - 10
        self.draw.text((right_x, bottom_y), "Tool by IncimathCal assisted by Claude Code",
                       font=font_large, fill=self.theme.text_stats, anchor="rs")
        self.draw.text((right_x, bottom_y - 30), self.theme.slogan,
                       font=font_large, fill=self.theme.text_stats, anchor="rs")

    # ------------------------------------------------------------------
    # Combo 里程碑标记（每 100 个物件）
    # ------------------------------------------------------------------

    def _draw_combo_milestones(self):
        from collections import defaultdict

        time_counts: dict[int, int] = defaultdict(int)
        for note in self.chart.note_list:
            if note.hand == 2:
                continue
            # 长条和 trill 以结尾为准
            if note.note_type in (2, 10, 64):
                t = note.end_ms
            else:
                t = note.start_ms
            time_counts[t] += 1

        sorted_times = sorted(time_counts.keys())

        count = 0
        milestones: list[tuple[int, int]] = []
        for t in sorted_times:
            prev_count = count
            count += time_counts[t]
            if count // 100 > prev_count // 100 and count >= 100:
                milestones.append((t, count))

        if not milestones or not getattr(self, "_segments", None):
            return

        orig_w = self.theme.margin_left + self.theme.track_width + self.theme.margin_right

        for i, (start_ms, end_ms, _) in enumerate(self._segments):
            col_x = i * orig_w
            track_left = col_x + self.theme.margin_left

            for t, cnt in milestones:
                if not (start_ms <= t <= end_ms):
                    continue
                y = self._segment_time_to_y(t, start_ms)
                if y < self.theme.track_reserved_top or y > self.coord.canvas_height - self.theme.track_reserved_bottom:
                    continue
                self.draw.text((track_left - 10, y), str(cnt),
                               font=self.theme.font_bpm, fill=(100, 255, 120, 255), anchor="rm")

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------

    def save(self, path: str, **kwargs):
        if self.im:
            rgb = Image.new("RGB", self.im.size, (18, 18, 24))
            rgb.paste(self.im, mask=self.im.split()[3])
            rgb.save(path, "PNG", **kwargs)

    def show(self):
        if self.im:
            self.im.show()

    @property
    def size(self) -> Tuple[int, int]:
        return self.im.size if self.im else (0, 0)
