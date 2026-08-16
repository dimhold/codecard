from __future__ import annotations

import pytest
from PIL import Image

from codecard import load_theme, render_card, render_file
from codecard.cli import main, parse_highlight
from codecard.guard import Guard, LeakDetected

SNIPPET = """SELECT id, total
FROM orders
WHERE total > 100
ORDER BY total DESC;
"""

LEAKY = "package com.acmebank.ledger;\nclass Ledger {}\n"


def test_default_card_is_the_theme_width_and_no_taller_than_the_theme():
    result = render_card(SNIPPET, lang="sql")
    theme = load_theme("midnight")
    assert result.width == theme.width == 1600
    assert theme.min_height <= result.height <= theme.height


def test_height_follows_the_content():
    short = render_card("one line", lang="text")
    tall = render_card("\n".join(f"line {i}" for i in range(20)), lang="text")
    assert short.height < tall.height


def test_a_long_snippet_stops_at_the_theme_height_and_says_so():
    with pytest.warns(RuntimeWarning, match="truncated"):
        result = render_card("\n".join(f"line {i}" for i in range(400)), lang="text")
    assert result.height == 900
    assert result.truncated


def test_explicit_size_is_respected():
    result = render_card(SNIPPET, lang="sql", width=1200, height=675)
    assert result.width == 1200
    assert result.height <= 675


def test_output_file_is_written_and_opens_as_a_png(tmp_path):
    out = tmp_path / "card.png"
    result = render_card(SNIPPET, lang="sql", output=out)
    assert out.is_file()
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.size == result.size


def test_output_directory_is_created(tmp_path):
    out = tmp_path / "nested" / "deep" / "card.png"
    render_card(SNIPPET, lang="sql", output=out)
    assert out.is_file()


def test_theme_changes_the_background_pixel():
    dark = render_card(SNIPPET, lang="sql", theme="midnight")
    light = render_card(SNIPPET, lang="sql", theme="paper")
    assert dark.image.getpixel((2, 2)) == load_theme("midnight").background
    assert light.image.getpixel((2, 2)) == load_theme("paper").background


def test_a_theme_mapping_can_be_passed_straight_in():
    result = render_card(SNIPPET, lang="sql", theme={"extends": "paper", "background": "#010203"})
    assert result.image.getpixel((2, 2)) == (1, 2, 3)


def test_watermark_is_off_by_default_and_changes_the_image_when_on():
    plain = render_card(SNIPPET, lang="sql")
    marked = render_card(SNIPPET, lang="sql", watermark="made with codecard")
    assert plain.theme.watermark.visible is False
    assert marked.theme.watermark.visible is True
    assert plain.image.tobytes() != marked.image.tobytes()
    assert marked.height > plain.height


def test_title_makes_the_card_taller():
    plain = render_card(SNIPPET, lang="sql")
    titled = render_card(SNIPPET, lang="sql", title="The fix, in full")
    assert titled.height > plain.height


def test_highlight_changes_pixels():
    plain = render_card(SNIPPET, lang="sql")
    banded = render_card(SNIPPET, lang="sql", highlight=[2])
    assert plain.image.tobytes() != banded.image.tobytes()


def test_line_numbers_can_be_turned_off():
    with_numbers = render_card(SNIPPET, lang="sql", line_numbers=True)
    without = render_card(SNIPPET, lang="sql", line_numbers=False)
    assert with_numbers.image.tobytes() != without.image.tobytes()


def test_font_size_is_reported_and_inside_the_theme_range():
    theme = load_theme("midnight")
    result = render_card(SNIPPET, lang="sql")
    assert theme.font.min_size <= result.font_size <= theme.font.max_size


def test_tabs_become_spaces():
    result = render_card("\tindented", lang="text")
    assert result.line_count == 1


# --------------------------------------------------------------------------- #
# the guard, through the render path
# --------------------------------------------------------------------------- #
def test_render_refuses_a_leaky_snippet_by_default():
    with pytest.raises(LeakDetected):
        render_card(LEAKY, lang="java")


def test_render_proceeds_when_the_guard_is_off():
    result = render_card(LEAKY, lang="java", guard="off")
    assert result.width == 1600
    assert result.findings == []


def test_warn_mode_renders_and_reports():
    with pytest.warns(RuntimeWarning):
        result = render_card(LEAKY, lang="java", guard="warn")
    assert [f.rule for f in result.findings] == ["package-declaration"]


def test_a_guard_object_can_be_passed_in():
    result = render_card(LEAKY, lang="java", guard=Guard(mode="off"))
    assert result.findings == []


def test_config_guard_applies_when_no_argument_is_given():
    result = render_card(LEAKY, lang="java", config={"guard": "off"})
    assert result.findings == []


# --------------------------------------------------------------------------- #
# files and the CLI
# --------------------------------------------------------------------------- #
def test_render_file_guesses_the_language(tmp_path):
    path = tmp_path / "query.sql"
    path.write_text(SNIPPET, encoding="utf-8")
    plain = render_file(path, theme={"line_numbers": {"enabled": False}})
    as_text = render_card(SNIPPET, lang="text", theme={"line_numbers": {"enabled": False}})
    assert plain.image.tobytes() != as_text.image.tobytes()


@pytest.mark.parametrize(
    "spec,expected",
    [("", set()), ("4", {4}), ("4,5", {4, 5}), ("9-12", {9, 10, 11, 12}), ("2, 4-5", {2, 4, 5})],
)
def test_parse_highlight(spec, expected):
    assert parse_highlight(spec) == expected


def test_cli_renders_a_file(tmp_path, capsys):
    src = tmp_path / "query.sql"
    src.write_text(SNIPPET, encoding="utf-8")
    out = tmp_path / "card.png"
    code = main([str(src), "-o", str(out), "--title", "Query", "--highlight", "2"])
    assert code == 0
    assert out.is_file()
    assert "1600x" in capsys.readouterr().out


def test_cli_default_output_sits_next_to_the_input(tmp_path):
    src = tmp_path / "query.sql"
    src.write_text(SNIPPET, encoding="utf-8")
    assert main([str(src), "-q"]) == 0
    assert (tmp_path / "query.png").is_file()


def test_cli_refuses_a_leaky_file_with_exit_code_2(tmp_path, capsys):
    src = tmp_path / "Ledger.java"
    src.write_text(LEAKY, encoding="utf-8")
    code = main([str(src), "-o", str(tmp_path / "out.png")])
    assert code == 2
    assert not (tmp_path / "out.png").exists()
    assert "refusing to render" in capsys.readouterr().err


def test_cli_allow_leaks_renders_anyway(tmp_path):
    src = tmp_path / "Ledger.java"
    src.write_text(LEAKY, encoding="utf-8")
    out = tmp_path / "out.png"
    assert main([str(src), "-o", str(out), "--allow-leaks", "-q"]) == 0
    assert out.is_file()


def test_cli_check_mode_renders_nothing(tmp_path, capsys):
    src = tmp_path / "Ledger.java"
    src.write_text(LEAKY, encoding="utf-8")
    assert main([str(src), "--check"]) == 2
    assert not (tmp_path / "Ledger.png").exists()

    clean = tmp_path / "ok.sql"
    clean.write_text(SNIPPET, encoding="utf-8")
    assert main([str(clean), "--check"]) == 0
    assert "clean" in capsys.readouterr().out


def test_cli_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.sql")]) == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_lists(capsys):
    assert main(["--list-themes"]) == 0
    out = capsys.readouterr().out
    assert "midnight" in out and "paper" in out

    assert main(["--list-languages"]) == 0
    assert "python" in capsys.readouterr().out

    assert main(["--list-rules"]) == 0
    assert "credential-literal" in capsys.readouterr().out


def test_cli_dump_theme_is_a_valid_theme_file(tmp_path, capsys):
    assert main(["--dump-theme", "paper"]) == 0
    dumped = tmp_path / "dumped.yaml"
    dumped.write_text(capsys.readouterr().out, encoding="utf-8")
    assert load_theme(dumped).background == load_theme("paper").background


def test_cli_reads_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _FakeStdin(SNIPPET))
    monkeypatch.chdir(tmp_path)
    assert main(["-", "--lang", "sql", "-q"]) == 0
    assert (tmp_path / "card.png").is_file()


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text
