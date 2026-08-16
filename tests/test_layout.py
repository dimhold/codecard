from __future__ import annotations

from codecard.layout import fit, wrap_lines


def char_measure(width_per_char: float = 10.0):
    """A monospace font where every glyph is the same width. Enough to test
    geometry without opening a font file."""
    return lambda text: len(text) * width_per_char


def test_short_lines_are_untouched():
    lines = wrap_lines(["one", "two"], char_measure(), max_px=100)
    assert [(item.number, item.text) for item in lines] == [(1, "one"), (2, "two")]


def test_long_line_wraps_and_continuations_lose_the_number():
    lines = wrap_lines(["aaa bbb ccc ddd"], char_measure(), max_px=70)
    assert lines[0].number == 1
    assert all(item.number is None for item in lines[1:])
    assert len(lines) > 1


def test_wrapped_pieces_keep_all_the_words():
    raw = "alpha beta gamma delta epsilon"
    lines = wrap_lines([raw], char_measure(), max_px=100)
    joined = " ".join(item.text.strip() for item in lines)
    assert joined.split() == raw.split()


def test_no_piece_is_wider_than_the_budget():
    measure = char_measure()
    lines = wrap_lines(["alpha beta gamma delta epsilon zeta"], measure, max_px=120)
    assert all(measure(item.text) <= 120 for item in lines)


def test_continuations_are_indented():
    lines = wrap_lines(["aaa bbb ccc ddd eee"], char_measure(), max_px=80)
    assert lines[1].text.startswith("    ")
    assert lines[1].is_continuation


def test_leading_indentation_is_kept_on_the_first_piece():
    lines = wrap_lines(["        return compute(a, b, c, d)"], char_measure(), max_px=200)
    assert lines[0].text.startswith("        ")


def test_a_single_word_longer_than_the_line_is_hard_cut():
    measure = char_measure()
    lines = wrap_lines(["x" * 50], measure, max_px=100)
    assert len(lines) >= 5
    assert all(measure(item.text) <= 100 for item in lines)
    assert "".join(item.text.strip() for item in lines) == "x" * 50


def test_blank_lines_survive():
    lines = wrap_lines(["a", "", "b"], char_measure(), max_px=100)
    assert [item.text for item in lines] == ["a", "", "b"]


def measure_at(size: int):
    return lambda text: len(text) * size * 0.6


def test_fit_picks_the_largest_size_that_needs_no_wrapping():
    layout = fit(
        ["short line"],
        measure_at,
        max_width=1000,
        max_height=1000,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    assert layout.font_size == 30
    assert not layout.wrapped
    assert not layout.truncated


def test_fit_steps_down_for_a_wide_line():
    layout = fit(
        ["x" * 90],
        measure_at,
        max_width=1000,
        max_height=1000,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    assert 12 <= layout.font_size < 30
    assert not layout.wrapped


def test_fit_wraps_only_when_nothing_fits():
    layout = fit(
        ["y" * 400],
        measure_at,
        max_width=600,
        max_height=1000,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    assert layout.font_size == 12
    assert layout.wrapped


def test_fit_truncates_when_the_box_is_too_short():
    layout = fit(
        ["z" * 400] * 40,
        measure_at,
        max_width=600,
        max_height=200,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    assert layout.truncated
    assert len(layout.lines) * layout.line_height <= 200


def test_fit_reserves_room_for_the_gutter():
    wide = fit(
        ["a" * 50],
        measure_at,
        max_width=1000,
        max_height=1000,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    narrow = fit(
        ["a" * 50],
        measure_at,
        max_width=1000,
        max_height=1000,
        min_size=12,
        max_size=30,
        line_spacing=8,
        gutter_at=lambda size: size * 4.0,
    )
    assert narrow.font_size < wide.font_size


def test_fit_handles_an_empty_snippet():
    layout = fit(
        [],
        measure_at,
        max_width=500,
        max_height=500,
        min_size=12,
        max_size=30,
        line_spacing=8,
    )
    assert layout.lines
