"""Language definitions for the highlighter.

The highlighting is deliberately crude: strings, numbers, keywords, comments.
A real parser per language would be a lot of code and would change almost no
pixels at this size, so a language here is four small facts, which also means
you can add one in five lines of YAML.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .errors import LanguageError


@dataclass(frozen=True)
class Language:
    """Everything the tokenizer knows about a language."""

    name: str
    keywords: Tuple[str, ...] = ()
    line_comment: Tuple[str, ...] = ()
    block_comment: bool = False
    case_sensitive: bool = True
    quotes: Tuple[str, ...] = ('"', "'")
    numbers: bool = True

    @property
    def keyword_set(self) -> frozenset:
        if self.case_sensitive:
            return frozenset(self.keywords)
        return frozenset(k.lower() for k in self.keywords)

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> "Language":
        """Build a language from a config file block."""
        unknown = set(data) - {
            "keywords",
            "line_comment",
            "block_comment",
            "case_sensitive",
            "quotes",
            "numbers",
            "extends",
        }
        if unknown:
            raise LanguageError(f"language {name!r}: unknown key(s) {sorted(unknown)}")

        base: Optional[Language] = None
        if "extends" in data:
            base = get_language(str(data["extends"]))

        def pick(key: str, fallback: Any) -> Any:
            if key in data:
                return data[key]
            return fallback

        keywords = pick("keywords", base.keywords if base else ())
        if isinstance(keywords, str):
            keywords = keywords.split()
        line_comment = pick("line_comment", base.line_comment if base else ())
        if isinstance(line_comment, str):
            line_comment = [line_comment]
        quotes = pick("quotes", base.quotes if base else ('"', "'"))
        if isinstance(quotes, str):
            quotes = list(quotes)

        return cls(
            name=name,
            keywords=tuple(str(k) for k in keywords),
            line_comment=tuple(str(c) for c in line_comment),
            block_comment=bool(pick("block_comment", base.block_comment if base else False)),
            case_sensitive=bool(pick("case_sensitive", base.case_sensitive if base else True)),
            quotes=tuple(str(q) for q in quotes),
            numbers=bool(pick("numbers", base.numbers if base else True)),
        )


def _kw(text: str) -> Tuple[str, ...]:
    return tuple(text.split())


BUILTIN: Dict[str, Language] = {}


def _add(lang: Language, *aliases: str) -> None:
    BUILTIN[lang.name] = lang
    for alias in aliases:
        BUILTIN[alias] = lang


_add(Language(name="text", numbers=False, quotes=()))

# Log output: no keywords, but levels and paths read better without string
# colouring, so quotes stay off and only numbers are picked out.
_add(Language(name="log", quotes=(), numbers=True), "logs", "output", "console")

_add(
    Language(
        name="python",
        keywords=_kw(
            """False None True and as assert async await break class continue def del elif else except
            finally for from global if import in is lambda nonlocal not or pass raise return try while
            with yield match case self cls"""
        ),
        line_comment=("#",),
        case_sensitive=True,
    ),
    "py",
)

_add(
    Language(
        name="javascript",
        keywords=_kw(
            """const let var function return if else for while do class extends implements interface type
            enum import export from default new await async try catch finally throw switch case break
            continue public private protected readonly static null undefined true false this super as of
            in typeof instanceof delete void yield satisfies keyof"""
        ),
        line_comment=("//",),
        block_comment=True,
    ),
    "js",
    "ts",
    "typescript",
    "tsx",
    "jsx",
)

_add(
    Language(
        name="java",
        keywords=_kw(
            """public private protected static final class interface enum record void return new if else
            for while do try catch finally throw throws import package extends implements this super null
            true false int long short byte char double float boolean String var abstract synchronized
            transient volatile native instanceof switch case default break continue assert sealed
            permits yield"""
        ),
        line_comment=("//",),
        block_comment=True,
    ),
    "kotlin",
    "kt",
    "scala",
    "csharp",
    "cs",
)

_add(
    Language(
        name="sql",
        keywords=_kw(
            """ALTER TABLE COLUMN TYPE SELECT FROM WHERE INSERT INTO VALUES UPDATE SET DELETE CREATE DROP
            INDEX UNIQUE PRIMARY FOREIGN REFERENCES KEY CONSTRAINT NOT NULL DEFAULT VARCHAR TEXT INTEGER
            BIGINT SMALLINT NUMERIC DECIMAL BOOLEAN TIMESTAMP DATE JSONB UUID ADD RENAME TO ORDER BY
            GROUP HAVING LIMIT OFFSET NULLS LAST FIRST DESC ASC JOIN LEFT RIGHT INNER OUTER FULL ON AS
            AND OR IS IN IF EXISTS BETWEEN LIKE CASE WHEN THEN ELSE END WITH UNION ALL DISTINCT COUNT SUM AVG
            MIN MAX COALESCE CAST BEGIN COMMIT ROLLBACK EXPLAIN ANALYZE VACUUM RETURNING CONFLICT DO
            NOTHING"""
        ),
        line_comment=("--",),
        block_comment=True,
        case_sensitive=False,
    ),
    "postgres",
    "mysql",
)

_add(
    Language(
        name="go",
        keywords=_kw(
            """break case chan const continue default defer else fallthrough for func go goto if import
            interface map package range return select struct switch type var nil true false error string
            int int64 float64 bool byte rune make new append len cap"""
        ),
        line_comment=("//",),
        block_comment=True,
    ),
    "golang",
)

_add(
    Language(
        name="rust",
        keywords=_kw(
            """as async await break const continue crate dyn else enum extern false fn for if impl in let
            loop match mod move mut pub ref return self Self static struct super trait true type unsafe
            use where while Some None Ok Err Result Option Vec String str u8 u32 u64 i32 i64 f64 bool"""
        ),
        line_comment=("//",),
        block_comment=True,
    ),
    "rs",
)

_add(
    Language(
        name="shell",
        keywords=_kw(
            """if then else elif fi for while do done case esac function return exit export local set
            unset echo cd source trap read shift"""
        ),
        line_comment=("#",),
    ),
    "sh",
    "bash",
    "zsh",
)

_add(Language(name="json", keywords=_kw("true false null"), quotes=('"',)))

_add(
    Language(
        name="yaml",
        keywords=_kw("true false null yes no on off"),
        line_comment=("#",),
        case_sensitive=False,
    ),
    "yml",
)

_add(
    Language(
        name="diff",
        keywords=(),
        line_comment=(),
        quotes=(),
        numbers=False,
    ),
    "patch",
)


def list_languages() -> Tuple[str, ...]:
    """Canonical names plus aliases, sorted, for ``--list-languages``."""
    return tuple(sorted(BUILTIN))


def get_language(name: str, extra: Optional[Mapping[str, Language]] = None) -> Language:
    """Look up a language by name or alias.

    ``extra`` holds languages defined in the user's config file and wins over the
    built-ins, so you can redefine ``sql`` for your dialect without forking.
    """
    key = (name or "text").strip().lower()
    if extra and key in extra:
        return extra[key]
    if key in BUILTIN:
        return BUILTIN[key]
    known: Iterable[str] = sorted(set(BUILTIN) | set(extra or {}))
    close = difflib.get_close_matches(key, list(known), n=3)
    hint = f" Did you mean {close[0]!r}?" if close else ""
    raise LanguageError(f"unknown language {name!r}.{hint} Try --list-languages.")


def languages_from_config(data: Optional[Mapping[str, Any]]) -> Dict[str, Language]:
    """Turn the ``languages:`` block of a config file into a lookup table."""
    out: Dict[str, Language] = {}
    if not data:
        return out
    if not isinstance(data, Mapping):
        raise LanguageError(f"languages: expected a mapping, got {type(data).__name__}")
    for name, block in data.items():
        if not isinstance(block, Mapping):
            raise LanguageError(f"language {name!r}: expected a mapping")
        out[str(name).lower()] = Language.from_dict(str(name).lower(), block)
    return out
