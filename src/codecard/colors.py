"""Colour parsing.

Themes are written by humans in a text file, so a colour can be ``"#0b0f14"``,
``"#0bf"`` or ``[11, 15, 20]``. Everything inside the renderer is an ``(r, g, b)``
tuple.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence, Tuple

RGB = Tuple[int, int, int]

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ColorError(ValueError):
    """A colour value that cannot be read as a colour."""


def parse_color(value: Any, *, where: str = "color") -> RGB:
    """Turn a theme value into an ``(r, g, b)`` tuple.

    >>> parse_color("#0b0f14")
    (11, 15, 20)
    >>> parse_color("#0bf")
    (0, 187, 255)
    >>> parse_color([11, 15, 20])
    (11, 15, 20)
    """
    if isinstance(value, (tuple, list)):
        if len(value) != 3 or not all(isinstance(c, int) for c in value):
            raise ColorError(f"{where}: expected three integers 0-255, got {value!r}")
        for c in value:
            if not 0 <= c <= 255:
                raise ColorError(f"{where}: channel out of range 0-255 in {value!r}")
        r, g, b = value
        return (r, g, b)
    if isinstance(value, str):
        m = _HEX.match(value.strip())
        if not m:
            raise ColorError(
                f'{where}: expected a hex colour like "#0b0f14" or three integers, got {value!r}'
            )
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    raise ColorError(f"{where}: expected a colour, got {type(value).__name__}")


def parse_optional_color(value: Any, *, where: str = "color") -> Optional[RGB]:
    """Same as :func:`parse_color` but ``None`` stays ``None`` (means "draw nothing")."""
    if value is None:
        return None
    return parse_color(value, where=where)


def to_hex(color: Sequence[int]) -> str:
    """``(11, 15, 20)`` back to ``"#0b0f14"``, used when dumping a theme."""
    r, g, b = color
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """Blend two colours. ``t=0`` is ``a``, ``t=1`` is ``b``."""
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )
