"""The ``codecard`` command.

    codecard snippet.sql -o fix.png --title "The fix, in full" --highlight 4,5

Exit codes: ``0`` rendered, ``2`` the guard refused, ``1`` anything else.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence, Set

from . import __version__
from .config import (
    Config,
    Theme,
    builtin_theme_names,
    find_config,
    load_config,
    load_theme,
)
from .errors import CodecardError
from .guard import Guard, LeakDetected, normalize_mode, rule_table
from .languages import BUILTIN, list_languages
from .render import guess_language, render_card

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_LEAK = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codecard",
        description="Render a code, log or error snippet as a card for a social feed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  codecard fix.sql\n"
            "  codecard fix.sql -o fix.png --title 'The fix, in full' --highlight 4,5\n"
            "  git diff | codecard - --lang diff --theme paper\n"
            "  codecard trace.log --theme ember --guard warn\n"
        ),
    )
    p.add_argument("input", nargs="?", help="file to render, or - for stdin")
    p.add_argument("-o", "--output", help="output image (default: <input>.png)")
    p.add_argument("-t", "--theme", help="built-in theme name or a path to a theme file")
    p.add_argument("-l", "--lang", help="language for highlighting (default: from the extension)")
    p.add_argument("--title", default=None, help="small caption above the panel")
    p.add_argument("--highlight", default="", help="1-based lines to band, e.g. 4,5,9-12")
    p.add_argument("--width", type=int, help="card width in pixels")
    p.add_argument("--height", type=int, help="maximum card height in pixels")
    p.add_argument("--watermark", help="watermark text (off unless you pass this)")

    numbers = p.add_mutually_exclusive_group()
    numbers.add_argument(
        "--numbers", dest="numbers", action="store_true", default=None, help="force the gutter on"
    )
    numbers.add_argument(
        "--no-numbers", dest="numbers", action="store_false", help="drop the line-number gutter"
    )

    p.add_argument(
        "--guard",
        choices=["error", "warn", "off", "on"],
        help="what to do when the snippet identifies a codebase (default: error)",
    )
    p.add_argument(
        "--allow-leaks",
        action="store_true",
        help="shorthand for --guard off; only for genuinely public code",
    )
    p.add_argument("--check", action="store_true", help="run the guard and render nothing")
    p.add_argument("-c", "--config", help="config file (default: codecard.yaml if there is one)")
    p.add_argument("--no-config", action="store_true", help="ignore any config file on disk")
    p.add_argument("--list-themes", action="store_true", help="list built-in themes and exit")
    p.add_argument("--list-languages", action="store_true", help="list languages and exit")
    p.add_argument("--list-rules", action="store_true", help="list guard rules and exit")
    p.add_argument("--dump-theme", metavar="NAME", help="print a theme as YAML, ready to edit")
    p.add_argument("-q", "--quiet", action="store_true", help="print nothing on success")
    p.add_argument("--version", action="version", version=f"codecard {__version__}")
    return p


def parse_highlight(spec: str) -> Set[int]:
    """``"4,5,9-12"`` to ``{4, 5, 9, 10, 11, 12}``."""
    out: Set[int] = set()
    for part in (spec or "").replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part.lstrip("-"):
            lo_s, _, hi_s = part.partition("-")
            lo, hi = int(lo_s), int(hi_s)
            if hi < lo:
                lo, hi = hi, lo
            out.update(range(lo, hi + 1))
        else:
            out.add(int(part))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list_themes:
            _print_themes()
            return EXIT_OK
        if args.list_languages:
            _print_languages()
            return EXIT_OK
        if args.list_rules:
            for name, why in rule_table().items():
                print(f"{name:22} {why}")
            return EXIT_OK
        if args.dump_theme:
            _dump_theme(args.dump_theme)
            return EXIT_OK

        if not args.input:
            parser.print_help()
            return EXIT_ERROR

        config = _resolve_config(args)
        source, source_path = _read_input(args.input)
        guard = _resolve_guard(args, config)

        if args.check:
            findings = guard.scan(source)
            if not findings:
                print("clean: nothing in this snippet identifies a codebase")
                return EXIT_OK
            _report(findings)
            return EXIT_LEAK

        lang = args.lang or (guess_language(source_path) if source_path else None)
        output = Path(args.output) if args.output else _default_output(source_path)

        result = render_card(
            source,
            lang=lang,
            title=args.title if args.title is not None else "",
            highlight=parse_highlight(args.highlight),
            theme=args.theme,
            config=config,
            guard=guard,
            line_numbers=args.numbers,
            watermark=args.watermark,
            width=args.width,
            height=args.height,
            output=output,
        )
    except LeakDetected as exc:
        _report(exc.findings)
        return EXIT_LEAK
    except CodecardError as exc:
        print(f"codecard: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (OSError, ValueError) as exc:
        print(f"codecard: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not args.quiet:
        w, h = result.size
        notes = []
        if result.wrapped:
            notes.append("wrapped")
        if result.truncated:
            notes.append("truncated")
        if result.findings:
            notes.append(f"{len(result.findings)} guard warning(s)")
        suffix = f" [{', '.join(notes)}]" if notes else ""
        print(f"{result.path}  {w}x{h}  {result.font_size}px  {result.line_count} lines{suffix}")
        for finding in result.findings:
            print(f"  warning: {finding}", file=sys.stderr)
    return EXIT_OK


def _resolve_config(args: argparse.Namespace) -> Config:
    if args.no_config:
        return Config.default()
    if args.config:
        return load_config(args.config)
    found = find_config()
    return load_config(found) if found else Config.default()


def _resolve_guard(args: argparse.Namespace, config: Config) -> Guard:
    guard = config.guard
    mode = None
    if args.guard:
        mode = normalize_mode(args.guard)
    if args.allow_leaks:
        mode = "off"
    if mode is not None:
        guard = Guard(mode=mode, rules=guard.rules, allow=guard.allow)
    return guard


def _read_input(spec: str):
    if spec == "-":
        return sys.stdin.read(), None
    path = Path(spec)
    if not path.is_file():
        raise CodecardError(f"no such file: {path}")
    return path.read_text(encoding="utf-8", errors="replace"), path


def _default_output(source_path: Optional[Path]) -> Path:
    if source_path is None:
        return Path("card.png")
    return source_path.with_suffix(".png")


def _print_themes() -> None:
    for name in builtin_theme_names():
        theme = load_theme(name)
        print(f"{name:10} {theme.description}")


def _print_languages() -> None:
    canonical: dict = {}
    for alias, lang in BUILTIN.items():
        canonical.setdefault(lang.name, []).append(alias)
    for name in sorted(canonical):
        aliases = sorted(a for a in canonical[name] if a != name)
        extra = f"  (also: {', '.join(aliases)})" if aliases else ""
        print(f"{name}{extra}")
    _ = list_languages()


def _dump_theme(name: str) -> None:
    theme: Theme = load_theme(name)
    try:
        import yaml

        print(yaml.safe_dump(theme.to_dict(), sort_keys=False, allow_unicode=True).rstrip())
    except ImportError:  # pragma: no cover - PyYAML is a dependency
        import json

        print(json.dumps(theme.to_dict(), indent=2))


def _report(findings: Sequence) -> None:
    print("codecard: refusing to render, this snippet identifies a codebase", file=sys.stderr)
    for finding in findings:
        why = f"  ({finding.why})" if getattr(finding, "why", "") else ""
        print(f"  {finding}{why}", file=sys.stderr)
    print(
        "edit the snippet, or pass --guard off if it is genuinely public code",
        file=sys.stderr,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
