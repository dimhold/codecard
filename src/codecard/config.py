"""Themes and config files.

A theme is one flat-ish mapping of colours, sizes and font choices. Nothing in it
is required: every key falls back to the default theme, so a five line file is a
valid theme and so is a hundred line one.

Precedence, lowest to highest::

    built-in default  ->  named built-in theme  ->  `extends:` chain  ->
    your theme file  ->  the config file's inline theme  ->  explicit arguments
"""
from __future__ import annotations

import difflib
import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .colors import RGB, parse_color, parse_optional_color, to_hex
from .errors import ConfigError, ThemeError
from .guard import Guard
from .languages import Language, languages_from_config
from .tokenizer import TokenKind

THEME_DIR = Path(__file__).resolve().parent / "themes"

CONFIG_NAMES = ("codecard.yaml", "codecard.yml", "codecard.json", ".codecard.yaml")

ThemeSpec = Union[str, Path, Mapping[str, Any], "Theme", None]

DEFAULT_THEME_NAME = "midnight"

#: Every key codecard understands, with the value it uses when you say nothing.
DEFAULT_THEME: Dict[str, Any] = {
    "name": "custom",
    "description": "",
    "width": 1600,
    "height": 900,
    "min_height": 320,
    "padding": 56,
    "background": "#0b0f14",
    "panel": {"color": "#101620", "radius": 14, "border": None, "padding": [28, 24]},
    "title": {"color": "#e2e8f0", "size": 30, "font": "sans_bold", "gap": 22},
    "font": {
        "mono": "bundled",
        "mono_bold": "bundled",
        "sans": "bundled",
        "sans_bold": "bundled",
        "min_size": 12,
        "max_size": 30,
        "line_spacing": 8,
    },
    "line_numbers": {"enabled": True, "color": "#566474", "width": 3},
    "tokens": {
        "text": "#e2e8f0",
        "keyword": "#c678dd",
        "string": "#98c379",
        "number": "#d19a66",
        "comment": "#5c6a7a",
    },
    "highlight": {"background": "#241a12", "bar": "#e8a860", "bar_width": 4},
    "watermark": {
        "enabled": False,
        "text": "",
        "color": "#7c88ff",
        "size": 19,
        "font": "mono",
        "gap": 24,
    },
}


# --------------------------------------------------------------------------- #
# theme pieces
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PanelStyle:
    color: RGB
    radius: int
    border: Optional[RGB]
    padding_x: int
    padding_y: int


@dataclass(frozen=True)
class TitleStyle:
    color: RGB
    size: int
    font: str
    gap: int


@dataclass(frozen=True)
class FontStyle:
    mono: str
    mono_bold: str
    sans: str
    sans_bold: str
    min_size: int
    max_size: int
    line_spacing: int

    def spec(self, role: str) -> str:
        return {
            "mono": self.mono,
            "mono_bold": self.mono_bold,
            "sans": self.sans,
            "sans_bold": self.sans_bold,
        }[role]


@dataclass(frozen=True)
class GutterStyle:
    enabled: bool
    color: RGB
    width: int


@dataclass(frozen=True)
class TokenStyle:
    text: RGB
    keyword: RGB
    string: RGB
    number: RGB
    comment: RGB

    def color(self, kind: TokenKind) -> RGB:
        return getattr(self, kind.value)


@dataclass(frozen=True)
class HighlightStyle:
    background: RGB
    bar: RGB
    bar_width: int


@dataclass(frozen=True)
class WatermarkStyle:
    enabled: bool
    text: str
    color: RGB
    size: int
    font: str
    gap: int

    @property
    def visible(self) -> bool:
        return self.enabled and bool(self.text.strip())


@dataclass(frozen=True)
class Theme:
    """A resolved theme. Immutable; use :meth:`with_overrides` to tweak one."""

    name: str
    description: str
    width: int
    height: int
    min_height: int
    padding: int
    background: RGB
    panel: PanelStyle
    title: TitleStyle
    font: FontStyle
    line_numbers: GutterStyle
    tokens: TokenStyle
    highlight: HighlightStyle
    watermark: WatermarkStyle
    source: Optional[Path] = None

    # -- construction ------------------------------------------------------- #
    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, source: Optional[Path] = None) -> "Theme":
        """Merge ``data`` over the defaults and validate it."""
        merged = deep_merge(DEFAULT_THEME, dict(data))
        merged.pop("extends", None)
        _check_keys(merged, DEFAULT_THEME, path="")

        panel = merged["panel"]
        pad = panel.get("padding", [28, 24])
        if isinstance(pad, int):
            pad = [pad, pad]
        if not isinstance(pad, (list, tuple)) or len(pad) != 2:
            raise ThemeError("panel.padding: expected one number or [x, y]")

        title = merged["title"]
        font = merged["font"]
        gutter = merged["line_numbers"]
        tokens = merged["tokens"]
        highlight = merged["highlight"]
        watermark = merged["watermark"]

        for role in ("mono", "mono_bold", "sans", "sans_bold"):
            if not isinstance(font.get(role), str):
                raise ThemeError(f"font.{role}: expected a string, got {font.get(role)!r}")
        if int(font["min_size"]) > int(font["max_size"]):
            raise ThemeError("font.min_size is larger than font.max_size")
        roles = (("title.font", title["font"]), ("watermark.font", watermark["font"]))
        for role_key, value in roles:
            if value not in ("mono", "mono_bold", "sans", "sans_bold"):
                raise ThemeError(
                    f"{role_key}: expected mono, mono_bold, sans or sans_bold, got {value!r}"
                )

        return cls(
            name=str(merged["name"]),
            description=str(merged["description"]),
            width=_positive(merged["width"], "width"),
            height=_positive(merged["height"], "height"),
            min_height=_positive(merged["min_height"], "min_height"),
            padding=_positive(merged["padding"], "padding", allow_zero=True),
            background=parse_color(merged["background"], where="background"),
            panel=PanelStyle(
                color=parse_color(panel["color"], where="panel.color"),
                radius=int(panel["radius"]),
                border=parse_optional_color(panel.get("border"), where="panel.border"),
                padding_x=int(pad[0]),
                padding_y=int(pad[1]),
            ),
            title=TitleStyle(
                color=parse_color(title["color"], where="title.color"),
                size=int(title["size"]),
                font=str(title["font"]),
                gap=int(title["gap"]),
            ),
            font=FontStyle(
                mono=str(font["mono"]),
                mono_bold=str(font["mono_bold"]),
                sans=str(font["sans"]),
                sans_bold=str(font["sans_bold"]),
                min_size=int(font["min_size"]),
                max_size=int(font["max_size"]),
                line_spacing=int(font["line_spacing"]),
            ),
            line_numbers=GutterStyle(
                enabled=bool(gutter["enabled"]),
                color=parse_color(gutter["color"], where="line_numbers.color"),
                width=int(gutter["width"]),
            ),
            tokens=TokenStyle(
                text=parse_color(tokens["text"], where="tokens.text"),
                keyword=parse_color(tokens["keyword"], where="tokens.keyword"),
                string=parse_color(tokens["string"], where="tokens.string"),
                number=parse_color(tokens["number"], where="tokens.number"),
                comment=parse_color(tokens["comment"], where="tokens.comment"),
            ),
            highlight=HighlightStyle(
                background=parse_color(highlight["background"], where="highlight.background"),
                bar=parse_color(highlight["bar"], where="highlight.bar"),
                bar_width=int(highlight["bar_width"]),
            ),
            watermark=WatermarkStyle(
                enabled=bool(watermark["enabled"]),
                text=str(watermark["text"]),
                color=parse_color(watermark["color"], where="watermark.color"),
                size=int(watermark["size"]),
                font=str(watermark["font"]),
                gap=int(watermark["gap"]),
            ),
            source=source,
        )

    # -- editing ------------------------------------------------------------ #
    def with_overrides(self, **overrides: Any) -> "Theme":
        """A copy with a few plain arguments applied. Unset values are ignored,
        so a CLI can pass ``width=None`` and mean "leave it alone"."""
        theme = self
        width = overrides.get("width")
        height = overrides.get("height")
        if width:
            theme = replace(theme, width=int(width))
        if height:
            theme = replace(theme, height=int(height))
        line_numbers = overrides.get("line_numbers")
        if line_numbers is not None:
            gutter = replace(theme.line_numbers, enabled=bool(line_numbers))
            theme = replace(theme, line_numbers=gutter)
        watermark = overrides.get("watermark")
        if watermark is not None:
            theme = replace(theme, watermark=_watermark_override(theme.watermark, watermark))
        padding = overrides.get("padding")
        if padding is not None:
            theme = replace(theme, padding=int(padding))
        return theme

    def to_dict(self) -> Dict[str, Any]:
        """Round-trip back to something you can save as a theme file."""
        return {
            "name": self.name,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "min_height": self.min_height,
            "padding": self.padding,
            "background": to_hex(self.background),
            "panel": {
                "color": to_hex(self.panel.color),
                "radius": self.panel.radius,
                "border": to_hex(self.panel.border) if self.panel.border else None,
                "padding": [self.panel.padding_x, self.panel.padding_y],
            },
            "title": {
                "color": to_hex(self.title.color),
                "size": self.title.size,
                "font": self.title.font,
                "gap": self.title.gap,
            },
            "font": {
                "mono": self.font.mono,
                "mono_bold": self.font.mono_bold,
                "sans": self.font.sans,
                "sans_bold": self.font.sans_bold,
                "min_size": self.font.min_size,
                "max_size": self.font.max_size,
                "line_spacing": self.font.line_spacing,
            },
            "line_numbers": {
                "enabled": self.line_numbers.enabled,
                "color": to_hex(self.line_numbers.color),
                "width": self.line_numbers.width,
            },
            "tokens": {
                "text": to_hex(self.tokens.text),
                "keyword": to_hex(self.tokens.keyword),
                "string": to_hex(self.tokens.string),
                "number": to_hex(self.tokens.number),
                "comment": to_hex(self.tokens.comment),
            },
            "highlight": {
                "background": to_hex(self.highlight.background),
                "bar": to_hex(self.highlight.bar),
                "bar_width": self.highlight.bar_width,
            },
            "watermark": {
                "enabled": self.watermark.enabled,
                "text": self.watermark.text,
                "color": to_hex(self.watermark.color),
                "size": self.watermark.size,
                "font": self.watermark.font,
                "gap": self.watermark.gap,
            },
        }


def _watermark_override(current: WatermarkStyle, value: Any) -> WatermarkStyle:
    if value is False:
        return replace(current, enabled=False)
    if value is True:
        return replace(current, enabled=True)
    if isinstance(value, str):
        return replace(current, enabled=bool(value.strip()), text=value)
    if isinstance(value, Mapping):
        data = deep_merge(
            {
                "enabled": current.enabled,
                "text": current.text,
                "color": to_hex(current.color),
                "size": current.size,
                "font": current.font,
                "gap": current.gap,
            },
            dict(value),
        )
        return WatermarkStyle(
            enabled=bool(data["enabled"]),
            text=str(data["text"]),
            color=parse_color(data["color"], where="watermark.color"),
            size=int(data["size"]),
            font=str(data["font"]),
            gap=int(data["gap"]),
        )
    raise ThemeError(f"watermark: expected a string, a bool or a mapping, got {value!r}")


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge. Values in ``over`` win; nested dicts are merged
    rather than replaced, which is what makes a three line theme file useful."""
    out: Dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in over.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _check_keys(data: Mapping[str, Any], schema: Mapping[str, Any], path: str) -> None:
    """Reject unknown keys, with a suggestion. A typo in a theme file is
    otherwise invisible: the colour just silently stays default."""
    for key, value in data.items():
        if key not in schema:
            close = difflib.get_close_matches(str(key), list(schema), n=1)
            hint = f", did you mean {close[0]!r}?" if close else ""
            where = f"{path}{key}"
            raise ThemeError(f"unknown theme key {where!r}{hint}")
        if isinstance(schema[key], dict) and isinstance(value, Mapping):
            _check_keys(value, schema[key], path=f"{path}{key}.")


def _positive(value: Any, where: str, allow_zero: bool = False) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ThemeError(f"{where}: expected a number, got {value!r}") from exc
    if n < 0 or (n == 0 and not allow_zero):
        raise ThemeError(f"{where}: expected a positive number, got {n}")
    return n


def read_data_file(path: Path) -> Dict[str, Any]:
    """Read a YAML or JSON file into a dict."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - packaging guarantees it
            raise ConfigError(
                f"reading {path} needs PyYAML. Install codecard's dependencies, or use JSON."
            ) from exc
        data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return dict(data)


def builtin_theme_names() -> Tuple[str, ...]:
    return tuple(sorted(p.stem for p in THEME_DIR.glob("*.yaml")))


def builtin_theme_path(name: str) -> Optional[Path]:
    path = THEME_DIR / f"{name}.yaml"
    return path if path.is_file() else None


def load_theme(spec: ThemeSpec = None, *, relative_to: Optional[Path] = None) -> Theme:
    """Resolve anything that can name a theme into a :class:`Theme`.

    ``None`` gives the default built-in, a bare name gives a built-in, a path
    gives a file, and a mapping is used as is. ``extends:`` inside a file or a
    mapping pulls in another theme first.
    """
    if isinstance(spec, Theme):
        return spec
    if spec is None:
        spec = DEFAULT_THEME_NAME

    if isinstance(spec, Mapping):
        data = dict(spec)
        base = data.pop("extends", None)
        if base is None:
            return Theme.from_dict(data)
        parent = load_theme(base, relative_to=relative_to)
        return Theme.from_dict(deep_merge(parent.to_dict(), data), source=parent.source)

    text = str(spec)
    builtin = builtin_theme_path(text)
    if builtin is not None and os.sep not in text and "/" not in text:
        return _theme_from_file(builtin)

    path = Path(text).expanduser()
    if not path.is_absolute() and relative_to is not None:
        candidate = (relative_to / path).resolve()
        if candidate.is_file():
            path = candidate
    if path.is_file():
        return _theme_from_file(path)

    names = builtin_theme_names()
    close = difflib.get_close_matches(text, list(names), n=1)
    hint = f" Did you mean {close[0]!r}?" if close else ""
    raise ThemeError(
        f"no theme {text!r}: not a built-in ({', '.join(names)}) and not a file.{hint}"
    )


def _theme_from_file(path: Path) -> Theme:
    data = read_data_file(path)
    data.setdefault("name", path.stem)
    base = data.pop("extends", None)
    if base is not None:
        parent = load_theme(base, relative_to=path.parent)
        return Theme.from_dict(deep_merge(parent.to_dict(), data), source=path)
    return Theme.from_dict(data, source=path)


DEFAULT_KEYS = ("lang", "title", "line_numbers", "watermark", "width", "height", "highlight")


@dataclass
class Config:
    """A whole config file: theme, guard, extra languages and default options."""

    theme: Theme
    guard: Guard
    languages: Dict[str, Language]
    defaults: Dict[str, Any]
    source: Optional[Path] = None

    @classmethod
    def default(cls) -> "Config":
        return cls(theme=load_theme(), guard=Guard(), languages={}, defaults={})

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, source: Optional[Path] = None
    ) -> "Config":
        unknown = set(data) - {"theme", "guard", "languages", "defaults"}
        if unknown:
            known = ["theme", "guard", "languages", "defaults"]
            close = difflib.get_close_matches(sorted(unknown)[0], known, n=1)
            hint = f", did you mean {close[0]!r}?" if close else ""
            raise ConfigError(f"config: unknown key(s) {sorted(unknown)}{hint}")

        relative_to = source.parent if source is not None else None
        theme = load_theme(data.get("theme"), relative_to=relative_to)

        defaults = dict(data.get("defaults") or {})
        bad = set(defaults) - set(DEFAULT_KEYS)
        if bad:
            raise ConfigError(f"config defaults: unknown key(s) {sorted(bad)}")

        return cls(
            theme=theme,
            guard=Guard.from_config(data.get("guard")),
            languages=languages_from_config(data.get("languages")),
            defaults=defaults,
            source=source,
        )


def load_config(spec: Union[str, Path, Mapping[str, Any], Config, None]) -> Config:
    """Load a config file, a mapping, or nothing at all."""
    if isinstance(spec, Config):
        return spec
    if spec is None:
        return Config.default()
    if isinstance(spec, Mapping):
        return Config.from_dict(spec)
    path = Path(str(spec)).expanduser()
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    return Config.from_dict(read_data_file(path), source=path)


def find_config(start: Optional[Path] = None) -> Optional[Path]:
    """Look for a config file next to the work, then in the user config dir.

    Nothing is implicit beyond this: if it returns ``None``, codecard runs on
    its defaults.
    """
    here = (start or Path.cwd()).resolve()
    for directory in [here, *here.parents]:
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    for candidate in _user_config_paths():
        if candidate.is_file():
            return candidate
    return None


def _user_config_paths() -> List[Path]:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        roots = [Path(base) / "codecard"] if base else []
    elif sys.platform == "darwin":
        roots = [Path.home() / "Library" / "Application Support" / "codecard"]
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        roots = [Path(xdg) / "codecard"]
    return [root / name for root in roots for name in ("config.yaml", "config.yml", "config.json")]
