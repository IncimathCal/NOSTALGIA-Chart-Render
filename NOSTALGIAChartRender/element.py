"""
NOSTALGIA 谱面数据模型

定义 Note、Timing、Chart 三个核心类。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Timing:
    """BPM 变化事件"""
    time_ms: int
    bpm: float

    def __repr__(self) -> str:
        return f"Timing({self.time_ms}ms, {self.bpm:.2f}BPM)"


@dataclass(frozen=True, slots=True)
class Note:
    """音符"""
    index: int
    start_ms: int
    end_ms: int
    gate_time_ms: int
    scale_piano: int
    min_key_index: int
    max_key_index: int
    note_type: int
    hand: int
    param1: int = 0
    param2: int = 0

    @property
    def center_key(self) -> float:
        return (self.min_key_index + self.max_key_index) / 2.0

    @property
    def key_width(self) -> int:
        return self.max_key_index - self.min_key_index

    def is_glissando_head(self) -> bool:
        return self.note_type in (4, 12) and self.param1 == -1

    def is_glissando_tail(self) -> bool:
        return self.note_type in (4, 12) and self.param2 == -1

    def __repr__(self) -> str:
        names = {0: "Normal", 2: "Long", 4: "Glissando", 8: "Trill",
                 10: "Special", 12: "Chain", 64: "Tremolo"}
        return f"Note({names.get(self.note_type, self.note_type)}, {self.start_ms}ms, keys=[{self.min_key_index},{self.max_key_index}])"


class Chart:
    """谱面对象"""

    def __init__(self, header: dict, timing_list: list[Timing], note_list: list[Note]):
        self.header = header
        self.timing_list = sorted(timing_list, key=lambda t: t.time_ms)
        self.note_list = sorted(note_list, key=lambda n: (n.start_ms, n.min_key_index))

        self._end_time = max(
            (n.end_ms for n in self.note_list),
            default=header.get("finish_time_ms", 0)
        )

    @property
    def end_time(self) -> int:
        return self._end_time

    @property
    def first_bpm(self) -> float:
        return self.header.get("first_bpm", 120.0)

    @property
    def finish_time_ms(self) -> int:
        return self.header.get("finish_time_ms", self._end_time)

    def get_bpm_at(self, time_ms: int) -> float:
        bpm = self.first_bpm
        for timing in self.timing_list:
            if timing.time_ms <= time_ms:
                bpm = timing.bpm
            else:
                break
        return bpm

    def get_notes_by_type(self, note_type: int) -> Iterator[Note]:
        return (n for n in self.note_list if n.note_type == note_type)

    def get_key_range(self) -> tuple[int, int]:
        if not self.note_list:
            return 0, 0
        return (
            min(n.min_key_index for n in self.note_list),
            max(n.max_key_index for n in self.note_list),
        )

    def get_glissando_chains(self) -> list[list[Note]]:
        """
        解析 Glissando 链（type 4 和 type 12）。

        使用 param1/param2 中存储的 XML index 直接匹配前后节点，
        比基于时间接近的推断更精确。
        """
        gliss = [n for n in self.note_list if n.note_type in (4, 12) and n.hand != 2]
        if not gliss:
            return []

        # 建立 index -> note 的映射
        index_map: dict[int, Note] = {n.index: n for n in gliss}

        chains: list[list[Note]] = []
        visited = set()

        for note in gliss:
            if note in visited or note.param1 != -1:
                continue

            # 从链头开始遍历
            chain = []
            current = note
            while current is not None:
                chain.append(current)
                visited.add(current)
                if current.param2 == -1:
                    break
                current = index_map.get(current.param2)
                if current is None or current in visited:
                    break

            if len(chain) >= 2:
                chains.append(chain)

        return chains

    def __repr__(self) -> str:
        return f"Chart(notes={len(self.note_list)}, timings={len(self.timing_list)}, duration={self.end_time/1000:.1f}s)"
