"""Every error codecard raises on purpose."""
from __future__ import annotations


class CodecardError(Exception):
    """Base class, so a caller can catch everything this library raises."""


class ThemeError(CodecardError):
    """A theme file is malformed, or names a key codecard does not know."""


class ConfigError(CodecardError):
    """A config file is malformed."""


class FontError(CodecardError):
    """A font was requested by path and is not there."""


class LanguageError(CodecardError):
    """An unknown language name, or a broken custom language definition."""
