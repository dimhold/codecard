from __future__ import annotations

import json

import pytest

from codecard.colors import ColorError, parse_color, to_hex
from codecard.config import (
    DEFAULT_THEME,
    Config,
    Theme,
    builtin_theme_names,
    deep_merge,
    find_config,
    load_config,
    load_theme,
)
from codecard.errors import ConfigError, ThemeError


# --------------------------------------------------------------------------- #
# colours
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,expected",
    [
        ("#0b0f14", (11, 15, 20)),
        ("0b0f14", (11, 15, 20)),
        ("#0bf", (0, 187, 255)),
        ([11, 15, 20], (11, 15, 20)),
    ],
)
def test_parse_color(value, expected):
    assert parse_color(value) == expected


@pytest.mark.parametrize("value", ["#12345", "rebeccapurple", [1, 2], [1, 2, 300], None, 7])
def test_bad_colour_is_rejected(value):
    with pytest.raises(ColorError):
        parse_color(value)


def test_hex_round_trip():
    assert to_hex(parse_color("#c678dd")) == "#c678dd"


# --------------------------------------------------------------------------- #
# built-in themes
# --------------------------------------------------------------------------- #
def test_the_three_built_in_themes_are_there():
    assert set(builtin_theme_names()) == {"ember", "midnight", "paper"}


@pytest.mark.parametrize("name", ["midnight", "paper", "ember"])
def test_built_in_themes_load_and_describe_themselves(name):
    theme = load_theme(name)
    assert theme.name == name
    assert theme.description
    assert theme.width > 0 and theme.height > 0


def test_default_theme_is_midnight():
    assert load_theme().name == "midnight"


def test_watermark_is_off_in_every_built_in_theme():
    for name in builtin_theme_names():
        assert load_theme(name).watermark.visible is False


def test_unknown_theme_name_suggests_a_close_one():
    with pytest.raises(ThemeError) as exc:
        load_theme("midnigth")
    assert "midnight" in str(exc.value)


# --------------------------------------------------------------------------- #
# user themes
# --------------------------------------------------------------------------- #
def test_a_three_line_theme_file_is_valid(tmp_path):
    path = tmp_path / "mine.yaml"
    path.write_text("background: '#000000'\ntokens:\n  keyword: '#ff0000'\n", encoding="utf-8")
    theme = load_theme(path)
    assert theme.background == (0, 0, 0)
    assert theme.tokens.keyword == (255, 0, 0)
    # untouched keys keep the default
    assert theme.tokens.string == parse_color(DEFAULT_THEME["tokens"]["string"])
    assert theme.name == "mine"


def test_theme_can_extend_a_built_in(tmp_path):
    path = tmp_path / "loud.yaml"
    path.write_text("extends: paper\ntokens:\n  keyword: '#ff00ff'\n", encoding="utf-8")
    theme = load_theme(path)
    assert theme.tokens.keyword == (255, 0, 255)
    assert theme.background == load_theme("paper").background
    assert theme.panel.border == load_theme("paper").panel.border


def test_theme_can_extend_another_file(tmp_path):
    (tmp_path / "base.yaml").write_text("background: '#101010'\n", encoding="utf-8")
    child = tmp_path / "child.yaml"
    child.write_text("extends: base.yaml\npadding: 12\n", encoding="utf-8")
    theme = load_theme(child)
    assert theme.background == (16, 16, 16)
    assert theme.padding == 12


def test_json_theme_file(tmp_path):
    path = tmp_path / "mine.json"
    path.write_text(json.dumps({"width": 1200, "height": 800}), encoding="utf-8")
    theme = load_theme(path)
    assert (theme.width, theme.height) == (1200, 800)


def test_unknown_theme_key_is_reported_with_a_suggestion(tmp_path):
    path = tmp_path / "typo.yaml"
    path.write_text("backgound: '#000000'\n", encoding="utf-8")
    with pytest.raises(ThemeError) as exc:
        load_theme(path)
    assert "background" in str(exc.value)


def test_unknown_nested_theme_key_is_reported_with_its_path(tmp_path):
    path = tmp_path / "typo.yaml"
    path.write_text("tokens:\n  keywords: '#ff0000'\n", encoding="utf-8")
    with pytest.raises(ThemeError) as exc:
        load_theme(path)
    assert "tokens.keywords" in str(exc.value)


def test_bad_size_is_rejected():
    with pytest.raises(ThemeError):
        Theme.from_dict({"width": 0})


def test_min_size_above_max_size_is_rejected():
    with pytest.raises(ThemeError):
        Theme.from_dict({"font": {"min_size": 40, "max_size": 20}})


def test_unknown_font_role_for_the_title_is_rejected():
    with pytest.raises(ThemeError):
        Theme.from_dict({"title": {"font": "comic"}})


def test_theme_round_trips_through_a_dict():
    theme = load_theme("ember")
    again = Theme.from_dict(theme.to_dict())
    assert again.to_dict() == theme.to_dict()


def test_panel_padding_accepts_one_number():
    theme = Theme.from_dict({"panel": {"padding": 10}})
    assert (theme.panel.padding_x, theme.panel.padding_y) == (10, 10)


# --------------------------------------------------------------------------- #
# overrides
# --------------------------------------------------------------------------- #
def test_overrides_win_over_the_theme():
    theme = load_theme("midnight").with_overrides(width=1200, height=675)
    assert (theme.width, theme.height) == (1200, 675)


def test_none_overrides_change_nothing():
    base = load_theme("midnight")
    same = base.with_overrides(width=None, height=None, line_numbers=None, watermark=None)
    assert same.to_dict() == base.to_dict()


def test_watermark_override_from_a_string_turns_it_on():
    theme = load_theme("midnight").with_overrides(watermark="@dimhold")
    assert theme.watermark.visible
    assert theme.watermark.text == "@dimhold"


def test_watermark_override_from_a_mapping():
    theme = load_theme("midnight").with_overrides(
        watermark={"enabled": True, "text": "acme", "size": 24}
    )
    assert theme.watermark.size == 24 and theme.watermark.text == "acme"


def test_watermark_false_turns_it_off():
    theme = load_theme("midnight").with_overrides(watermark="x").with_overrides(watermark=False)
    assert theme.watermark.visible is False


def test_line_numbers_override():
    assert load_theme("midnight").with_overrides(line_numbers=False).line_numbers.enabled is False


def test_deep_merge_keeps_untouched_branches():
    merged = deep_merge({"a": {"x": 1, "y": 2}, "b": 3}, {"a": {"y": 9}})
    assert merged == {"a": {"x": 1, "y": 9}, "b": 3}


def test_deep_merge_does_not_mutate_the_base():
    base = {"a": {"x": 1}}
    deep_merge(base, {"a": {"x": 2}})
    assert base == {"a": {"x": 1}}


# --------------------------------------------------------------------------- #
# config files
# --------------------------------------------------------------------------- #
CONFIG_YAML = """
theme:
  extends: paper
  padding: 40
guard:
  mode: warn
  disable: [private-ip]
languages:
  hcl:
    keywords: [resource]
    line_comment: "#"
defaults:
  lang: sql
  line_numbers: false
"""


def test_config_file_wires_everything_together(tmp_path):
    path = tmp_path / "codecard.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    config = load_config(path)
    assert config.theme.padding == 40
    assert config.theme.background == load_theme("paper").background
    assert config.guard.mode == "warn"
    assert "private-ip" not in {r.name for r in config.guard.rules}
    assert "hcl" in config.languages
    assert config.defaults["lang"] == "sql"


def test_config_theme_can_be_a_file_path(tmp_path):
    (tmp_path / "mine.yaml").write_text("background: '#010203'\n", encoding="utf-8")
    path = tmp_path / "codecard.yaml"
    path.write_text("theme: mine.yaml\n", encoding="utf-8")
    assert load_config(path).theme.background == (1, 2, 3)


def test_config_defaults_reject_unknown_keys(tmp_path):
    path = tmp_path / "codecard.yaml"
    path.write_text("defaults:\n  langauge: sql\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_config_rejects_unknown_top_level_keys(tmp_path):
    path = tmp_path / "codecard.yaml"
    path.write_text("themes: paper\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_config_file_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_no_config_means_defaults():
    config = load_config(None)
    assert config.theme.name == "midnight"
    assert config.guard.mode == "error"
    assert config.languages == {}


def test_config_accepts_a_plain_mapping():
    config = Config.from_dict({"theme": "ember", "guard": "off"})
    assert config.theme.name == "ember"
    assert config.guard.mode == "off"


def test_find_config_looks_in_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / "codecard.yaml").write_text("theme: paper\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    found = find_config()
    assert found is not None and found.name == "codecard.yaml"
