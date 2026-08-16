"""Regenerate every image in docs/ from the sources in this repository.

    python scripts/build_docs_images.py

Nothing in docs/ is hand made, and nothing in it comes from a screenshot tool.
The hero is codecard rendering its own guard.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codecard import render_card, render_file  # noqa: E402

DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"


def extract(path: Path, start: str, end: str) -> str:
    """The block of a source file between two markers, dedented."""
    lines = path.read_text(encoding="utf-8").splitlines()
    first = next(i for i, line in enumerate(lines) if start in line)
    last = next(i for i, line in enumerate(lines[first:], first) if end in line)
    return textwrap.dedent("\n".join(lines[first : last + 1]))


def main() -> int:
    DOCS.mkdir(exist_ok=True)

    # The hero: the function that decides what codecard will not render.
    hero = extract(ROOT / "src" / "codecard" / "guard.py", "def scan(self", "return findings")
    render_card(
        hero,
        lang="python",
        title="codecard rendering its own leak guard",
        highlight=[8, 9],
        output=DOCS / "hero.png",
    )

    # Before: pasted straight out of the editor, guard switched off on purpose.
    render_file(
        EXAMPLES / "before-leaky.java",
        lang="text",
        title="before: pasted straight from the editor",
        line_numbers=False,
        guard="off",
        output=DOCS / "before.png",
    )

    # After: the same change, with everything that names a codebase removed.
    render_file(
        EXAMPLES / "after-clean.java",
        title="after: same change, nothing that names a repo",
        highlight=[3, 4],
        output=DOCS / "after.png",
    )

    for theme in ("midnight", "paper", "ember"):
        render_file(
            EXAMPLES / "migration.sql",
            theme=theme,
            title=f"theme: {theme}",
            highlight=[9],
            width=1200,
            output=DOCS / f"theme-{theme}.png",
        )

    render_file(
        EXAMPLES / "build.log",
        lang="log",
        theme="ember",
        title="a failing run, on the theme built for logs",
        width=1200,
        output=DOCS / "log.png",
    )

    render_file(
        EXAMPLES / "migration.sql",
        theme=EXAMPLES / "custom-theme.yaml",
        title="a theme file of your own, eleven lines long",
        width=1200,
        output=DOCS / "custom-theme.png",
    )

    for path in sorted(DOCS.glob("*.png")):
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
