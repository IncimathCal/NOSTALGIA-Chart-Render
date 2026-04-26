"""
节奏分析：推断相邻 note 的时间间隔对应的分音类型。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .element import Chart

THRESHOLD_MS = 3.5


@dataclass
class BeatNote:
    time_ms: int
    duration: int
    divide: int = -1
    beyond_full: bool = False
    has_dot: bool = False
    is_triplet: bool = False

    def format(self) -> str:
        if self.beyond_full or self.divide <= 0:
            return ""
        text = f"1/{self.divide}"
        if self.has_dot:
            text += "."
        return text


def _is_close(a: float, b: float, threshold: float = THRESHOLD_MS) -> bool:
    return abs(a - b) <= threshold


def analyze_duration(duration_ms: float, bpm: float) -> Optional[BeatNote]:
    if bpm <= 0:
        return None

    full = 60_000 * 4 / bpm
    result = BeatNote(time_ms=0, duration=int(duration_ms))

    if duration_ms > full:
        result.beyond_full = True
        return result

    if _is_close(duration_ms, full):
        result.divide = 1
        return result

    for d in [2, 4, 8, 16, 32, 64]:
        t = full / d
        if _is_close(duration_ms, t):
            result.divide = d
            return result
        if _is_close(duration_ms, t * 1.5):
            result.divide = d
            result.has_dot = True
            return result

    for d in [3, 6, 12, 24, 48]:
        t = full / d
        if _is_close(duration_ms, t):
            result.divide = d
            result.is_triplet = True
            return result

    return None


def analyze_chart_rhythm(chart: Chart) -> list[BeatNote]:
    times: set[int] = set()
    for note in chart.note_list:
        times.add(note.start_ms)
        if note.note_type == 2:
            times.add(note.end_ms)

    sorted_times = sorted(times)
    result: list[BeatNote] = []

    for i in range(len(sorted_times) - 1):
        delta = sorted_times[i + 1] - sorted_times[i]
        if delta <= 3:
            continue

        bpm = chart.get_bpm_at(sorted_times[i])
        beat = analyze_duration(delta, bpm)
        if beat is None:
            beat = analyze_duration(delta, chart.first_bpm)

        if beat is not None:
            beat.time_ms = sorted_times[i]
            beat.duration = delta
            result.append(beat)

    return result
