"""Finding a font on somebody else's machine.

Three ways to name a font in a theme, in the order most people want them:

``bundled``   the DejaVu faces shipped inside the package. Identical output on
              Linux, macOS and Windows, and no setup. This is the default.
``system``    hunt through the platform font directories for a good face, and
              fall back to bundled if nothing is found.
a name        ``"JetBrains Mono"`` or ``"Menlo"``: same hunt, but for that
              family. Falls back to bundled with a warning.
a path        ``"/usr/share/fonts/truetype/Foo.ttf"``: used as given, and a missing
              file is an error rather than a surprise.
"""
from __future__ import annotations

import os
import sys
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import ImageFont

from .errors import FontError

BUNDLED_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

#: Role names a theme may use.
ROLES = ("mono", "mono_bold", "sans", "sans_bold")

BUNDLED_FILES: Dict[str, str] = {
    "mono": "DejaVuSansMono.ttf",
    "mono_bold": "DejaVuSansMono-Bold.ttf",
    "sans": "DejaVuSans.ttf",
    "sans_bold": "DejaVuSans-Bold.ttf",
}

# Tried in order. Nothing here is required to exist.
SYSTEM_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "mono": (
        "JetBrainsMono-Regular",
        "FiraCode-Regular",
        "CascadiaMono",
        "SFMono-Regular",
        "Menlo",
        "DejaVuSansMono",
        "LiberationMono-Regular",
        "NotoSansMono-Regular",
        "Consolas",
        "consola",
        "cour",
    ),
    "mono_bold": (
        "JetBrainsMono-Bold",
        "FiraCode-Bold",
        "CascadiaMono-Bold",
        "Menlo-Bold",
        "DejaVuSansMono-Bold",
        "LiberationMono-Bold",
        "consolab",
        "courbd",
    ),
    "sans": (
        "Inter-Regular",
        "SF-Pro-Text-Regular",
        "HelveticaNeue",
        "DejaVuSans",
        "LiberationSans-Regular",
        "NotoSans-Regular",
        "segoeui",
        "arial",
    ),
    "sans_bold": (
        "Inter-Bold",
        "SF-Pro-Text-Bold",
        "HelveticaNeue-Bold",
        "DejaVuSans-Bold",
        "LiberationSans-Bold",
        "NotoSans-Bold",
        "segoeuib",
        "arialbd",
    ),
}


def system_font_dirs() -> List[Path]:
    """Where fonts live on this platform. Missing directories are dropped."""
    home = Path.home()
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        local = os.environ.get("LOCALAPPDATA")
        candidates = [windir / "Fonts"]
        if local:
            candidates.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        candidates = [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ]
    else:
        xdg = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
        candidates = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path(xdg) / "fonts",
            home / ".fonts",
        ]
    return [p for p in candidates if p.is_dir()]


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _system_index() -> Dict[str, Path]:
    """``{normalised stem: path}`` for every font file on the machine.

    Built once per process. On a machine with thousands of fonts this is a few
    hundred milliseconds, and only ``system`` or a named family pays for it.
    """
    index: Dict[str, Path] = {}
    for directory in system_font_dirs():
        for pattern in ("*.ttf", "*.otf", "*.ttc"):
            for path in directory.rglob(pattern):
                index.setdefault(_normalize(path.stem), path)
    return index


def bundled_path(role: str) -> Path:
    """Path to the DejaVu face shipped for ``role``."""
    if role not in BUNDLED_FILES:
        raise FontError(f"unknown font role {role!r}, expected one of {ROLES}")
    path = BUNDLED_DIR / BUNDLED_FILES[role]
    if not path.is_file():
        raise FontError(
            f"bundled font missing at {path}. A source checkout keeps them in "
            "src/codecard/assets/fonts."
        )
    return path


def find_system_font(names: Sequence[str]) -> Optional[Path]:
    """First of ``names`` that exists on this machine, or ``None``."""
    index = _system_index()
    for name in names:
        hit = index.get(_normalize(name))
        if hit is not None:
            return hit
    return None


def resolve_font(spec: str, role: str) -> Path:
    """Turn a theme's font spec into a file path."""
    if role not in BUNDLED_FILES:
        raise FontError(f"unknown font role {role!r}, expected one of {ROLES}")
    value = (spec or "bundled").strip()

    if value.lower() in ("bundled", "packaged", "default"):
        return bundled_path(role)

    if value.lower() in ("system", "auto"):
        found = find_system_font(SYSTEM_CANDIDATES[role])
        return found if found is not None else bundled_path(role)

    looks_like_path = (
        os.sep in value
        or "/" in value
        or value.lower().endswith((".ttf", ".otf", ".ttc"))
    )
    if looks_like_path:
        path = Path(value).expanduser()
        if not path.is_file():
            raise FontError(f"font file not found: {path}")
        return path

    found = find_system_font([value, value.replace(" ", "-"), value.replace(" ", "")])
    if found is not None:
        return found
    warnings.warn(
        f"font {value!r} not found on this system, falling back to the bundled face",
        RuntimeWarning,
        stacklevel=2,
    )
    return bundled_path(role)


@lru_cache(maxsize=128)
def load_font(spec: str, role: str, size: int) -> ImageFont.FreeTypeFont:
    """Resolve and open a font. Cached, because fitting opens the same face at
    a dozen sizes."""
    path = resolve_font(spec, role)
    try:
        return ImageFont.truetype(str(path), size)
    except OSError as exc:
        raise FontError(f"could not open font {path}: {exc}") from exc
