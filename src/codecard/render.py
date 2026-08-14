"""Drawing the card.

The height follows the content: a card that is two thirds empty looks like a
mistake. The width is fixed by the theme, because a feed crops on width and
consistency across a series of posts is most of the point.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PIL import Image, ImageDraw

from .colors import RGB
from .config import Config, Theme, ThemeSpec, load_config, load_theme
from .fonts import load_font
from .guard import Finding, Guard, LeakDetected
from .languages import Language, get_language
from .layout import Layout, fit
from .tokenizer import tokenize_line

GuardSpec = Union[Guard, str, bool, Mapping[str, Any], None]
ConfigSpec = Union[Config, str, Path, Mapping[str, Any], None]


@dataclass
class RenderResult:
    """What a render produced, plus what the guard thought of it."""

    image: Image.Image
    theme: Theme
    font_size: int
    line_count: int
    wrapped: bool
    truncated: bool
    findings: List[Finding] = field(default_factory=list)
    path: Optional[Path] = None

    @property
    def size(self) -> Tuple[int, int]:
        return self.image.size

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height


def render_file(
    path: Union[str, Path],
    *,
    lang: Optional[str] = None,
    **kwargs: Any,
) -> RenderResult:
    """Render a file. The language is guessed from the extension unless given."""
    src = Path(path)
    text = src.read_text(encoding="utf-8")
    return render_card(text, lang=lang if lang is not None else guess_language(src), **kwargs)


def render_card(
    source: str,
    *,
    lang: Optional[str] = None,
    title: str = "",
    highlight: Iterable[int] = (),
    theme: ThemeSpec = None,
    config: ConfigSpec = None,
    guard: GuardSpec = None,
    line_numbers: Optional[bool] = None,
    watermark: Union[str, bool, Mapping[str, Any], None] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    output: Union[str, Path, None] = None,
) -> RenderResult:
    """Render a snippet as a card.

    ``source`` is the text itself. Everything else is optional::

        from codecard import render_card
        render_card(open("fix.sql").read(), lang="sql", title="The fix, in full",
                    highlight=[4, 5], output="fix.png")

    Raises :class:`~codecard.guard.LeakDetected` when the guard is in ``error``
    mode and the snippet identifies a codebase.
    """
    cfg = load_config(config)
    defaults = cfg.defaults

    resolved_theme = cfg.theme if theme is None else load_theme(theme)
    resolved_theme = resolved_theme.with_overrides(
        width=width if width is not None else defaults.get("width"),
        height=height if height is not None else defaults.get("height"),
        line_numbers=line_numbers if line_numbers is not None else defaults.get("line_numbers"),
        watermark=watermark if watermark is not None else defaults.get("watermark"),
    )

    if lang is None:
        lang = str(defaults.get("lang", "text"))
    if not title:
        title = str(defaults.get("title", ""))
    highlight_lines = set(int(n) for n in (highlight or defaults.get("highlight") or ()))

    active_guard = cfg.guard if guard is None else _as_guard(guard)
    findings = active_guard.scan(source)
    if findings and active_guard.mode == "error":
        raise LeakDetected(findings)
    if findings and active_guard.mode == "warn":
        warnings.warn(
            "codecard: snippet identifies a codebase ("
            + "; ".join(str(f) for f in findings)
            + ")",
            RuntimeWarning,
            stacklevel=2,
        )

    language = get_language(lang, cfg.languages)
    raw = source.replace("\t", "    ").rstrip("\n").split("\n")

    image, layout = _draw(raw, language, resolved_theme, title, highlight_lines)

    saved: Optional[Path] = None
    if output is not None:
        saved = Path(output)
        if saved.parent and not saved.parent.exists():
            saved.parent.mkdir(parents=True, exist_ok=True)
        image.save(saved)

    return RenderResult(
        image=image,
        theme=resolved_theme,
        font_size=layout.font_size,
        line_count=len(layout.lines),
        wrapped=layout.wrapped,
        truncated=layout.truncated,
        findings=findings,
        path=saved,
    )


def guess_language(path: Union[str, Path]) -> str:
    """Extension to language name. Unknown extensions become ``text``."""
    suffix = Path(path).suffix.lower().lstrip(".")
    table = {
        "py": "python",
        "pyi": "python",
        "js": "javascript",
        "mjs": "javascript",
        "cjs": "javascript",
        "ts": "typescript",
        "tsx": "tsx",
        "jsx": "jsx",
        "java": "java",
        "kt": "kotlin",
        "kts": "kotlin",
        "scala": "scala",
        "cs": "csharp",
        "sql": "sql",
        "go": "go",
        "rs": "rust",
        "sh": "shell",
        "bash": "shell",
        "zsh": "shell",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "log": "log",
        "txt": "text",
        "diff": "diff",
        "patch": "diff",
    }
    return table.get(suffix, "text")


def _as_guard(spec: GuardSpec) -> Guard:
    if isinstance(spec, Guard):
        return spec
    return Guard.from_config(spec)


def _probe() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new("RGB", (1, 1)))


def _draw(
    raw: Sequence[str],
    language: Language,
    theme: Theme,
    title: str,
    highlight_lines: Set[int],
) -> Tuple[Image.Image, Layout]:
    probe = _probe()
    pad = theme.padding
    panel_pad_x = theme.panel.padding_x
    panel_pad_y = theme.panel.padding_y

    top = pad + ((theme.title.size + theme.title.gap) if title else 0)
    foot = (theme.watermark.size + theme.watermark.gap) if theme.watermark.visible else 0
    inner_w = theme.width - 2 * pad - 2 * panel_pad_x
    avail_h = theme.height - top - pad - foot - 2 * panel_pad_y
    if inner_w < 40 or avail_h < 20:
        raise ValueError(
            "nothing fits: width/height leave no room once padding and title are taken out"
        )

    def measure_at(size: int):
        font = load_font(theme.font.mono, "mono", size)
        return lambda text: probe.textlength(text, font=font)

    def gutter_at(size: int) -> float:
        if not theme.line_numbers.enabled:
            return 0.0
        font = load_font(theme.font.mono, "mono", size)
        return probe.textlength("0" * theme.line_numbers.width + " ", font=font)

    layout = fit(
        raw,
        measure_at,
        max_width=inner_w,
        max_height=avail_h,
        min_size=theme.font.min_size,
        max_size=theme.font.max_size,
        line_spacing=theme.font.line_spacing,
        gutter_at=gutter_at,
    )
    if layout.truncated:
        warnings.warn("codecard: snippet truncated to fit the card", RuntimeWarning, stacklevel=3)

    mono = load_font(theme.font.mono, "mono", layout.font_size)
    gutter_w = int(gutter_at(layout.font_size))

    content_h = len(layout.lines) * layout.line_height
    height = min(
        theme.height,
        max(theme.min_height, top + 2 * panel_pad_y + content_h + pad + foot),
    )

    image = Image.new("RGB", (theme.width, height), theme.background)
    draw = ImageDraw.Draw(image)

    if title:
        role = theme.title.font
        title_font = load_font(theme.font.spec(role), role, theme.title.size)
        draw.text((pad, pad), title, font=title_font, fill=theme.title.color)

    panel = (pad, top, theme.width - pad, height - pad - foot)
    draw.rounded_rectangle(
        panel,
        radius=theme.panel.radius,
        fill=theme.panel.color,
        outline=theme.panel.border,
        width=1 if theme.panel.border else 0,
    )

    x0 = panel[0] + panel_pad_x
    y = panel[1] + panel_pad_y
    for line in layout.lines:
        if line.number in highlight_lines:
            _band(draw, panel, y, layout.line_height, theme)
        if theme.line_numbers.enabled and line.number is not None:
            draw.text(
                (x0, y),
                str(line.number).rjust(theme.line_numbers.width),
                font=mono,
                fill=theme.line_numbers.color,
            )
        x = x0 + gutter_w
        for token in tokenize_line(line.text, language):
            color: RGB = theme.tokens.color(token.kind)
            draw.text((x, y), token.text, font=mono, fill=color)
            x += draw.textlength(token.text, font=mono)
        y += layout.line_height

    if theme.watermark.visible:
        mark_font = load_font(
            theme.font.spec(theme.watermark.font), theme.watermark.font, theme.watermark.size
        )
        text = theme.watermark.text
        mark_x = theme.width - pad - draw.textlength(text, font=mark_font)
        mark_y = panel[3] + theme.watermark.gap // 2
        draw.text((mark_x, mark_y), text, font=mark_font, fill=theme.watermark.color)

    return image, layout


def _band(
    draw: ImageDraw.ImageDraw,
    panel: Tuple[int, int, int, int],
    y: int,
    line_height: int,
    theme: Theme,
) -> None:
    """The warm band behind a highlighted line, plus its left bar."""
    draw.rectangle(
        [panel[0] + 8, y - 3, panel[2] - 8, y + line_height - 3],
        fill=theme.highlight.background,
    )
    draw.rectangle(
        [panel[0] + 8, y - 3, panel[0] + 8 + theme.highlight.bar_width, y + line_height - 3],
        fill=theme.highlight.bar,
    )
