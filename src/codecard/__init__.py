"""codecard: render a code, log or error snippet as a card for a social feed.

    from codecard import render_card
    render_card("SELECT 1;", lang="sql", output="card.png")

The library refuses by default to render a snippet that identifies a codebase.
See :mod:`codecard.guard`.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .colors import parse_color
from .config import (
    Config,
    Theme,
    builtin_theme_names,
    find_config,
    load_config,
    load_theme,
)
from .errors import CodecardError, ConfigError, FontError, LanguageError, ThemeError
from .guard import Finding, Guard, GuardRule, LeakDetected, rule_table, scan
from .languages import Language, get_language, list_languages
from .layout import Line, wrap_lines
from .render import RenderResult, guess_language, render_card, render_file
from .tokenizer import Token, TokenKind, tokenize_line

__all__ = [
    "__version__",
    "CodecardError",
    "Config",
    "ConfigError",
    "Finding",
    "FontError",
    "Guard",
    "GuardRule",
    "Language",
    "LanguageError",
    "LeakDetected",
    "Line",
    "RenderResult",
    "Theme",
    "ThemeError",
    "Token",
    "TokenKind",
    "builtin_theme_names",
    "find_config",
    "get_language",
    "guess_language",
    "list_languages",
    "load_config",
    "load_theme",
    "parse_color",
    "render_card",
    "render_file",
    "rule_table",
    "scan",
    "tokenize_line",
    "wrap_lines",
]
