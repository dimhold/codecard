from __future__ import annotations

import pytest

from codecard.errors import ConfigError
from codecard.guard import Guard, LeakDetected, default_rules, normalize_mode, rule_table, scan

# --------------------------------------------------------------------------- #
# things that must be caught
# --------------------------------------------------------------------------- #
LEAKY = {
    "package-declaration": "package com.acmebank.ledger.core;",
    "namespace-declaration": "namespace AcmeBank.Ledger.Core",
    "absolute-path": r"at C:\Users\dmitry\projects\ledger\src\main.java:44",
    "private-import": "import com.acmebank.ledger.OrderService;",
    "internal-host": "https://billing.acme.internal/api/v2/invoices",
    "private-ip": "connected to 10.42.7.19:5432",
    "credential-literal": 'api_key = "sk-live-9f2b1c7d4e"',
    "aws-access-key": "AKIAIOSFODNN7EXAMPLE",
    "private-key-block": "-----BEGIN RSA PRIVATE KEY-----",
    "jwt": "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP",
    "connection-string": "postgres://ledger:hunter2hunter2@db.acme.corp:5432/ledger",
}


@pytest.mark.parametrize("rule_name,snippet", sorted(LEAKY.items()))
def test_each_default_rule_catches_its_case(rule_name, snippet):
    findings = scan(snippet)
    assert rule_name in {f.rule for f in findings}, f"{rule_name} missed: {snippet}"


def test_every_default_rule_has_a_case_in_this_test():
    assert {r.name for r in default_rules()} == set(LEAKY)


def test_every_default_rule_explains_itself():
    assert all(why for why in rule_table().values())


# --------------------------------------------------------------------------- #
# things that must not be caught
# --------------------------------------------------------------------------- #
CLEAN = [
    "import java.util.List;",
    "import org.springframework.boot.SpringApplication;",
    "import org.junit.jupiter.api.Test;",
    "from dataclasses import dataclass",
    'fetch("https://github.com/dimhold/codecard")',
    "psql postgres://localhost:5432/dev",
    "2026-08-16 09:41:22 INFO started in 1.4s",
    "#!/usr/bin/env python3",
    "src/codecard/render.py:44: warning",
    'password = os.environ["DB_PASSWORD"]',
    'api_key = ""',
    "SELECT count(*) FROM orders WHERE total > 100;",
    "requests==2.31.0",
    "took 10.4s, 1200 rows",
]


@pytest.mark.parametrize("snippet", CLEAN)
def test_ordinary_code_is_not_flagged(snippet):
    assert scan(snippet) == []


def test_a_whole_clean_file_is_clean():
    text = "\n".join(CLEAN)
    assert Guard().scan(text) == []


# --------------------------------------------------------------------------- #
# behaviour
# --------------------------------------------------------------------------- #
def test_findings_carry_the_line_number():
    text = "ok\nok\napi_key = 'sk-live-abcdefgh'\n"
    findings = scan(text)
    assert [f.line for f in findings] == [3]


def test_error_mode_raises_and_carries_the_findings():
    with pytest.raises(LeakDetected) as exc:
        Guard().check("package com.acme.thing;")
    assert exc.value.findings[0].rule == "package-declaration"


def test_warn_mode_returns_findings_without_raising():
    findings = Guard(mode="warn").check("package com.acme.thing;")
    assert findings and findings[0].rule == "package-declaration"


def test_off_mode_finds_nothing_at_all():
    assert Guard(mode="off").check("package com.acme.thing;") == []
    assert Guard(mode="off").enabled is False


def test_disable_drops_one_rule():
    guard = Guard.from_config({"disable": ["private-ip"]})
    assert guard.scan("host 10.42.7.19") == []
    assert guard.scan("package com.acme.thing;")


def test_only_keeps_one_rule():
    guard = Guard.from_config({"only": ["credential-literal"]})
    assert guard.scan("package com.acme.thing;") == []
    assert guard.scan('token: "abcdefghij"')


def test_allow_pattern_exempts_a_match():
    guard = Guard.from_config({"allow": [r"docs\.acme\.internal"]})
    assert guard.scan("https://docs.acme.internal/readme") == []
    assert guard.scan("https://billing.acme.internal/api")


def test_custom_rule_is_added_to_the_defaults():
    guard = Guard.from_config(
        {"rules": [{"name": "ticket-id", "pattern": r"ACME-\d+", "why": "internal tracker"}]}
    )
    findings = guard.scan("fixes ACME-4412")
    assert findings[0].rule == "ticket-id"
    assert findings[0].why == "internal tracker"


def test_guard_from_a_bool_and_from_a_string():
    assert Guard.from_config(False).mode == "off"
    assert Guard.from_config(True).mode == "error"
    assert Guard.from_config("warn").mode == "warn"
    assert Guard.from_config(None).mode == "error"


@pytest.mark.parametrize(
    "value,expected",
    [("on", "error"), ("strict", "error"), ("warning", "warn"), ("no", "off"), ("0", "off")],
)
def test_mode_aliases(value, expected):
    assert normalize_mode(value) == expected


def test_unknown_mode_is_an_error():
    with pytest.raises(ConfigError):
        normalize_mode("maybe")


def test_unknown_rule_name_is_an_error():
    with pytest.raises(ConfigError):
        Guard.from_config({"disable": ["no-such-rule"]})


def test_unknown_guard_key_is_an_error():
    with pytest.raises(ConfigError):
        Guard.from_config({"modes": "warn"})


def test_bad_custom_regex_is_an_error():
    with pytest.raises(ConfigError):
        Guard.from_config({"rules": [{"name": "bad", "pattern": "([unclosed"}]})


def test_findings_are_sorted_by_line():
    text = "clean\npackage com.acme.a;\nclean\napi_key = 'sk-live-abcdefgh'"
    assert [f.line for f in scan(text)] == [2, 4]


def test_match_sample_is_truncated():
    long_secret = "token: '" + "x" * 300 + "'"
    assert len(scan(long_secret)[0].match) <= 80
