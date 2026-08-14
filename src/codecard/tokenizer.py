"""A one-line-at-a-time highlighter.

The scanner walks a line left to right and emits runs of text with a kind
attached. It has no state between lines, which is wrong for a multi-line string
and right for everything else you paste into a card, including a log tail that
starts in the middle of a stack trace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence

from .languages import Language


class TokenKind(str, Enum):
    """The five things the renderer knows how to colour."""

    TEXT = "text"
    KEYWORD = "keyword"
    STRING = "string"
    NUMBER = "number"
    COMMENT = "comment"


@dataclass(frozen=True)
class Token:
    text: str
    kind: TokenKind


_NUMBER = re.compile(r"0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?")
_WORD = re.compile(r"[A-Za-z_$][\w$]*")
_BLOCK_COMMENT_LINE = re.compile(r"\s*(?:/\*|\*/|\*(?!\w))")


def tokenize_line(line: str, lang: Language) -> List[Token]:
    """Split one line into coloured runs.

    Adjacent plain runs are merged, so ``x = y`` is three tokens and not eleven.
    """
    if lang.block_comment and _BLOCK_COMMENT_LINE.match(line) and line.strip():
        return [Token(line, TokenKind.COMMENT)]

    tokens: List[Token] = []
    plain: List[str] = []
    keywords = lang.keyword_set

    def flush() -> None:
        if plain:
            tokens.append(Token("".join(plain), TokenKind.TEXT))
            plain.clear()

    i = 0
    n = len(line)
    while i < n:
        rest = line[i:]

        comment = next((c for c in lang.line_comment if c and rest.startswith(c)), None)
        if comment is not None:
            flush()
            tokens.append(Token(rest, TokenKind.COMMENT))
            return tokens

        ch = line[i]

        if ch in lang.quotes:
            end = _string_end(line, i, ch)
            flush()
            tokens.append(Token(line[i:end], TokenKind.STRING))
            i = end
            continue

        if lang.numbers and ch.isdigit() and not _inside_word(line, i):
            m = _NUMBER.match(rest)
            if m:
                flush()
                tokens.append(Token(m.group(0), TokenKind.NUMBER))
                i += m.end()
                continue

        m = _WORD.match(rest)
        if m:
            word = m.group(0)
            probe = word if lang.case_sensitive else word.lower()
            if probe in keywords:
                flush()
                tokens.append(Token(word, TokenKind.KEYWORD))
            else:
                plain.append(word)
            i += len(word)
            continue

        plain.append(ch)
        i += 1

    flush()
    return tokens


def tokenize(lines: Sequence[str], lang: Language) -> List[List[Token]]:
    """Tokenize a whole snippet, one list of tokens per line."""
    return [tokenize_line(line, lang) for line in lines]


def _inside_word(line: str, i: int) -> bool:
    """True when the digit at ``i`` belongs to an identifier like ``sha256``."""
    if i == 0:
        return False
    prev = line[i - 1]
    return prev.isalnum() or prev in "_$."


def _string_end(line: str, start: int, quote: str) -> int:
    """Index just past the closing quote, or the end of the line if unterminated."""
    i = start + 1
    n = len(line)
    while i < n:
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == quote:
            return i + 1
        i += 1
    return n
