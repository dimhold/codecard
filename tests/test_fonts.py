from __future__ import annotations

import pytest

from codecard.errors import FontError
from codecard.fonts import BUNDLED_FILES, ROLES, bundled_path, load_font, resolve_font


@pytest.mark.parametrize("role", ROLES)
def test_every_role_has_a_bundled_face(role):
    path = bundled_path(role)
    assert path.is_file()
    assert path.suffix == ".ttf"


def test_bundled_is_the_default_and_is_platform_independent():
    for role in ROLES:
        assert resolve_font("bundled", role) == bundled_path(role)
        assert resolve_font("", role) == bundled_path(role)


def test_system_falls_back_to_bundled_when_nothing_matches(monkeypatch):
    monkeypatch.setattr("codecard.fonts.SYSTEM_CANDIDATES", {r: ("no-such-face",) for r in ROLES})
    assert resolve_font("system", "mono") == bundled_path("mono")


def test_a_named_family_that_is_missing_warns_and_falls_back():
    with pytest.warns(RuntimeWarning):
        assert resolve_font("Definitely Not Installed", "sans") == bundled_path("sans")


def test_a_font_path_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(FontError):
        resolve_font(str(tmp_path / "nope.ttf"), "mono")


def test_a_real_font_path_is_used_as_given():
    given = bundled_path("mono")
    assert resolve_font(str(given), "mono") == given


def test_unknown_role_is_an_error():
    with pytest.raises(FontError):
        resolve_font("bundled", "cursive")


def test_load_font_is_cached_and_measures_text():
    a = load_font("bundled", "mono", 20)
    b = load_font("bundled", "mono", 20)
    assert a is b
    assert a.getlength("xxxx") > a.getlength("xx")


def test_bundled_table_covers_exactly_the_roles():
    assert set(BUNDLED_FILES) == set(ROLES)
