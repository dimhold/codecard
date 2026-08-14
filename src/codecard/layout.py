"""Line wrapping and font fitting.

Both take a ``measure`` callback instead of a font, so the geometry can be tested
without rendering anything and so a future backend other than Pillow would not
need a rewrite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

Measure = Callable[[str], float]

_SPLIT = re.compile(r"(\s+)")


@dataclass(frozen=True)
class Line:
    """One drawn row. ``number`` is ``None`` on a wrapped continuation, so the
    gutter stays honest about which rows are real lines of the file."""

    number: Optional[int]
    text: str

    @property
    def is_continuation(self) -> bool:
        return self.number is None


@dataclass(frozen=True)
class Layout:
    """The result of fitting a snippet into a box."""

    font_size: int
    line_height: int
    lines: List[Line]
    wrapped: bool
    truncated: bool


def wrap_lines(
    raw: Sequence[str],
    measure: Measure,
    max_px: float,
    indent: str = "    ",
) -> List[Line]:
    """Wrap over-wide lines, marking the continuations."""
    out: List[Line] = []
    for n, line in enumerate(raw, 1):
        if not line.strip() or measure(line) <= max_px:
            out.append(Line(n, line))
            continue
        pieces = _wrap_one(line, measure, max_px, indent)
        out.append(Line(n, pieces[0]))
        out.extend(Line(None, piece) for piece in pieces[1:])
    return out


def _wrap_one(line: str, measure: Measure, max_px: float, indent: str) -> List[str]:
    out: List[str] = []
    cur = ""

    def push() -> None:
        nonlocal cur
        out.append(cur)
        cur = indent

    for token in filter(None, _SPLIT.split(line)):
        if token.isspace():
            # Leading indentation of the first segment is content. Whitespace at
            # a wrap point is not, and would push the continuation off centre.
            if (cur.strip() or not out) and measure(cur + token) <= max_px:
                cur += token
            continue
        if measure(cur + token) <= max_px:
            cur += token
            continue
        if cur.strip():
            push()
        if cur == indent and measure(cur + token) > max_px and measure(token) <= max_px:
            # The word fits on a line of its own. Keeping the continuation
            # indent here would cut a word that did not need cutting.
            cur = ""
        while measure(cur + token) > max_px:
            cut = _fit_prefix(cur, token, measure, max_px)
            if cut <= 0:
                break
            cur += token[:cut]
            token = token[cut:]
            push()
        cur += token

    out.append(cur)
    return out


def _fit_prefix(prefix: str, token: str, measure: Measure, max_px: float) -> int:
    """Largest ``k`` where ``prefix + token[:k]`` still fits. Binary search,
    because measuring a proportional-ish font per character is the slow part."""
    lo, hi = 0, len(token)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(prefix + token[:mid]) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return lo


def fit(
    raw: Sequence[str],
    measure_at: Callable[[int], Measure],
    *,
    max_width: float,
    max_height: float,
    min_size: int,
    max_size: int,
    line_spacing: int,
    gutter_at: Callable[[int], float] = lambda size: 0.0,
) -> Layout:
    """Pick the largest font size that needs no wrapping at all.

    A wrapped code line reads as a different line and misleads, so wrapping is a
    last resort: only when nothing in the size range fits does codecard drop to
    the smallest size and wrap, and only then can it truncate.
    """
    if max_size < min_size:
        min_size, max_size = max_size, min_size
    raw = list(raw) or [""]

    for size in range(max_size, min_size - 1, -1):
        measure = measure_at(size)
        line_height = size + line_spacing
        widest = max((measure(line) for line in raw), default=0.0)
        if widest <= max_width - gutter_at(size) and len(raw) * line_height <= max_height:
            return Layout(
                font_size=size,
                line_height=line_height,
                lines=[Line(i + 1, line) for i, line in enumerate(raw)],
                wrapped=False,
                truncated=False,
            )

    size = min_size
    measure = measure_at(size)
    line_height = size + line_spacing
    lines = wrap_lines(raw, measure, max(1.0, max_width - gutter_at(size)))
    truncated = False
    room = int(max_height // line_height)
    if room >= 1 and len(lines) > room:
        lines = lines[:room]
        truncated = True
    return Layout(
        font_size=size,
        line_height=line_height,
        lines=lines,
        wrapped=any(line.is_continuation for line in lines),
        truncated=truncated,
    )
