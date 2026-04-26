"""
NOSTALGIA Chart Render - 纹理加载器

从 assets 目录加载 note 纹理，按 note 类型应用颜色调色。
"""

from __future__ import annotations
import os
from typing import Optional

from PIL import Image, ImageOps


_ASSETS_DIR: Optional[str] = None


def set_assets_dir(path: str):
    """设置素材根目录（内含 notes/ 子目录）"""
    global _ASSETS_DIR
    _ASSETS_DIR = path


def _find_texture(*parts: str) -> Optional[str]:
    """在 assets/notes/ 下查找纹理文件"""
    if _ASSETS_DIR is None:
        return None
    path = os.path.join(_ASSETS_DIR, "notes", *parts)
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return path
    return None


class TextureLoader:
    def __init__(self):
        self._cache: dict[str, Image.Image] = {}
        self._ratio_cache: dict[str, float] = {}

    def _load(self, path: str) -> Image.Image:
        if path not in self._cache:
            self._cache[path] = Image.open(path).convert("RGBA")
        return self._cache[path].copy()

    @staticmethod
    def _compute_content_ratio(path: str) -> float:
        try:
            img = Image.open(path).convert("RGBA")
            alpha = img.split()[3]
            w, h = img.size
            nonempty = 0
            for x in range(w):
                if alpha.crop((x, 0, x + 1, h)).getextrema()[1] > 30:
                    nonempty += 1
            return nonempty / w
        except Exception:
            return 1.0

    def _resolve_path(self, note_type: int, key_width: float, center_key: float, hand: int = 0) -> str | None:
        base = self._base_name(note_type)
        direction = self._direction(hand)
        width_suffix = self._width_suffix(key_width)
        filename = self._file_name(base, direction, width_suffix)
        subdir = f"{base}{direction}"

        path = _find_texture(subdir, filename)
        if path is None:
            alt = f"{base[0]}{width_suffix}.png"
            path = _find_texture(base, alt)
        return path

    @staticmethod
    def _base_name(note_type: int) -> str:
        if note_type == 4:
            return "glissando"
        if note_type == 8:
            return "trill"
        if note_type == 10:
            return "white_forte"
        if note_type == 12:
            return "white"
        if note_type == 64:
            return "trill_forte"
        return "white"

    @staticmethod
    def _direction(hand: int) -> str:
        return "_l" if hand == 1 else "_r"

    @staticmethod
    def _width_suffix(key_width: float) -> str:
        w = max(1, min(10, int(round(key_width))))
        return f"_{w:02d}"

    @staticmethod
    def _file_name(base: str, direction: str, width_suffix: str) -> str:
        prefix = base[0]
        suffix = base.split("_", 1)[1] if "_" in base else ""
        if suffix:
            return f"{prefix}_{suffix}{direction}{width_suffix}.png"
        return f"{prefix}{direction}{width_suffix}.png"

    @staticmethod
    def _apply_gold(img: Image.Image) -> Image.Image:
        r, g, b, a = img.split()
        r = r.point(lambda i: min(255, int(i * 1.3)))
        g = g.point(lambda i: min(255, int(i * 1.15)))
        b = b.point(lambda i: int(i * 0.5))
        return Image.merge("RGBA", (r, g, b, a))

    @staticmethod
    def _apply_gray(img: Image.Image) -> Image.Image:
        gray = ImageOps.grayscale(img.convert("RGB")).convert("RGBA")
        _, _, _, a = img.split()
        return Image.merge("RGBA", (*gray.split()[:3], a))

    @staticmethod
    def _apply_orange(img: Image.Image) -> Image.Image:
        r, g, b, a = img.split()
        r = r.point(lambda i: min(255, int(i * 1.4)))
        g = g.point(lambda i: min(255, int(i * 0.9)))
        b = b.point(lambda i: int(i * 0.3))
        return Image.merge("RGBA", (r, g, b, a))

    def get_texture(
        self,
        note_type: int,
        key_width: float,
        center_key: float,
        hand: int = 0,
    ) -> Optional[Image.Image]:
        path = self._resolve_path(note_type, key_width, center_key, hand)
        if path is None:
            return None

        if path not in self._ratio_cache:
            self._ratio_cache[path] = self._compute_content_ratio(path)

        img = self._load(path)

        if note_type == 10:
            img = self._apply_gold(img)
        elif note_type == 12:
            img = self._apply_gray(img)
        elif note_type == 64:
            img = self._apply_orange(img)

        return img

    def get_content_ratio(
        self,
        note_type: int,
        key_width: float,
        center_key: float,
        hand: int = 0,
    ) -> float:
        path = self._resolve_path(note_type, key_width, center_key, hand)
        if path is None:
            return 1.0
        if path not in self._ratio_cache:
            self._ratio_cache[path] = self._compute_content_ratio(path)
        return self._ratio_cache[path]

    @staticmethod
    def _hand_suffix(hand: int) -> str:
        return "_l" if hand == 1 else "_r"

    def _resolve_long_end(self, key_width: float, hand: int = 0) -> str | None:
        suffix = self._hand_suffix(hand)
        w = max(1, min(10, int(round(key_width))))
        filename = f"end{suffix}_{w:02d}.png"
        for subdir in (f"common/long_end{suffix}", f"long_end{suffix}"):
            path = _find_texture(subdir, filename)
            if path:
                return path
        return None

    def _resolve_trill_forte(self, key_width: float, hand: int = 0) -> str | None:
        suffix = self._hand_suffix(hand)
        w = max(1, min(10, int(round(key_width))))
        filename = f"tr_forte{suffix}_{w:02d}.png"
        path = _find_texture(f"trill_forte{suffix}", filename)
        return path

    def get_long_end(self, key_width: float, hand: int = 0) -> Optional[Image.Image]:
        path = self._resolve_long_end(key_width, hand)
        return self._load(path) if path else None

    def get_trill_forte(self, key_width: float, hand: int = 0) -> Optional[Image.Image]:
        path = self._resolve_trill_forte(key_width, hand)
        return self._load(path) if path else None

    def get_long_end_ratio(self, key_width: float, hand: int = 0) -> float:
        path = self._resolve_long_end(key_width, hand)
        if path is None:
            return 1.0
        if path not in self._ratio_cache:
            self._ratio_cache[path] = self._compute_content_ratio(path)
        return self._ratio_cache[path]

    def get_trill_forte_ratio(self, key_width: float, hand: int = 0) -> float:
        path = self._resolve_trill_forte(key_width, hand)
        if path is None:
            return 1.0
        if path not in self._ratio_cache:
            self._ratio_cache[path] = self._compute_content_ratio(path)
        return self._ratio_cache[path]

    def _resolve_trill_piano(self, key_width: float, hand: int = 0) -> str | None:
        suffix = self._hand_suffix(hand)
        w = max(1, min(10, int(round(key_width))))
        filename = f"tr_piano{suffix}_{w:02d}.png"
        path = _find_texture(f"trill_piano{suffix}", filename)
        return path

    def get_trill_piano(self, key_width: float, hand: int = 0) -> Optional[Image.Image]:
        path = self._resolve_trill_piano(key_width, hand)
        return self._load(path) if path else None

    def get_trill_piano_ratio(self, key_width: float, hand: int = 0) -> float:
        path = self._resolve_trill_piano(key_width, hand)
        if path is None:
            return 1.0
        if path not in self._ratio_cache:
            self._ratio_cache[path] = self._compute_content_ratio(path)
        return self._ratio_cache[path]


_loader: Optional[TextureLoader] = None


def get_loader() -> TextureLoader:
    global _loader
    if _loader is None:
        _loader = TextureLoader()
    return _loader
