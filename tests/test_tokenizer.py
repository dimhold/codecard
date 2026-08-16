from __future__ import annotations

import pytest

from codecard.languages import Language, get_language, languages_from_config
from codecard.tokenizer import TokenKind, tokenize_line


def kinds(line: str, lang: str):
    return [(t.text, t.kind) for t in tokenize_line(line, get_language(lang))]


def test_plain_text_is_one_run():
    assert kinds("nothing to see here", "text") == [("nothing to see here", TokenKind.TEXT)]


def test_keyword_number_and_string():
    got = kinds('const limit = 42; const name = "orders";', "ts")
    assert ("const", TokenKind.KEYWORD) in got
    assert ("42", TokenKind.NUMBER) in got
    assert ('"orders"', TokenKind.STRING) in got


def test_adjacent_plain_runs_are_merged():
    tokens = tokenize_line("a = b + c", get_language("text"))
    assert len(tokens) == 1


def test_line_comment_takes_the_rest_of_the_line():
    got = kinds("x = 1  # why this is 2", "python")
    assert got[-1] == ("# why this is 2", TokenKind.COMMENT)
    assert ("1", TokenKind.NUMBER) in got


def test_sql_comment_prefix_is_two_dashes():
    got = kinds("SELECT 1 -- a note", "sql")
    assert got[-1][1] is TokenKind.COMMENT
    assert got[0] == ("SELECT", TokenKind.KEYWORD)


def test_sql_keywords_are_case_insensitive():
    assert kinds("select 1", "sql")[0][1] is TokenKind.KEYWORD


def test_python_keywords_are_case_sensitive():
    assert kinds("Import os", "python")[0][1] is TokenKind.TEXT


def test_comment_marker_inside_a_string_is_not_a_comment():
    got = kinds('url = "https://example.com/x"  // real comment', "ts")
    assert ('"https://example.com/x"', TokenKind.STRING) in got
    assert got[-1] == ("// real comment", TokenKind.COMMENT)


def test_block_comment_line_is_all_comment():
    assert kinds(" * @param id the order id", "java") == [
        (" * @param id the order id", TokenKind.COMMENT)
    ]


def test_digits_inside_an_identifier_are_not_numbers():
    got = kinds("sha256 = 1", "python")
    assert ("256", TokenKind.NUMBER) not in got
    assert ("1", TokenKind.NUMBER) in got


def test_hex_and_float_literals():
    got = kinds("mask = 0xff; ratio = 1.5e3", "ts")
    assert ("0xff", TokenKind.NUMBER) in got
    assert ("1.5e3", TokenKind.NUMBER) in got


def test_unterminated_string_runs_to_end_of_line():
    got = kinds('name = "orders', "ts")
    assert got[-1] == ('"orders', TokenKind.STRING)


def test_escaped_quote_stays_inside_the_string():
    got = kinds(r'msg = "say \"hi\" now" ok', "ts")
    assert (r'"say \"hi\" now"', TokenKind.STRING) in got


def test_log_language_has_no_string_colouring():
    got = kinds('2026-08-16 ERROR "boom"', "log")
    assert all(t[1] is not TokenKind.STRING for t in got)


def test_custom_language_from_config():
    extra = languages_from_config(
        {"hcl": {"keywords": ["resource", "variable"], "line_comment": "#"}}
    )
    lang = get_language("hcl", extra)
    got = [(t.text, t.kind) for t in tokenize_line('resource "x" {} # note', lang)]
    assert got[0] == ("resource", TokenKind.KEYWORD)
    assert got[-1] == ("# note", TokenKind.COMMENT)


def test_custom_language_can_extend_a_builtin():
    extra = languages_from_config({"mysql": {"extends": "sql", "keywords": ["SHOW", "ENGINE"]}})
    lang = extra["mysql"]
    assert lang.line_comment == ("--",)
    assert tokenize_line("SHOW ENGINE", lang)[0].kind is TokenKind.KEYWORD


def test_unknown_language_suggests_a_close_one():
    with pytest.raises(Exception) as exc:
        get_language("pyton")
    assert "python" in str(exc.value)


def test_keywords_may_be_written_as_one_string():
    lang = Language.from_dict("toy", {"keywords": "alpha beta"})
    assert lang.keywords == ("alpha", "beta")
