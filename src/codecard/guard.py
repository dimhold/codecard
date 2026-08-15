"""The leak guard.

A card is public and permanent. A package declaration, a build path with your
username in it or a token that was supposed to be a placeholder is the kind of
thing that only turns out to matter later, and by then the image is on someone
else's timeline and in three scrapers.

So the guard reads the snippet before anything is drawn and fails closed: by
default codecard refuses to render rather than warning. Every rule is a named
regex, every rule can be switched off, and you can add your own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Pattern, Sequence, Tuple

from .errors import ConfigError

MODES = ("error", "warn", "off")

# Package and namespace names, absolute paths, private-looking imports, internal
# hosts and credential-shaped literals. Each entry is (name, pattern, why).
_DEFAULT_RULE_SOURCE: Tuple[Tuple[str, str, str], ...] = (
    (
        "package-declaration",
        r"^[ \t]*package\s+[\w.]+\s*;",
        "a Java or Kotlin package name is your company and product, spelled out",
    ),
    (
        "namespace-declaration",
        r"^[ \t]*namespace\s+[\w.]+\s*[;{]?\s*$",
        "a C# or PHP namespace is the same giveaway as a package name",
    ),
    (
        "absolute-path",
        r"(?<![A-Za-z])[A-Za-z]:[\\/](?!/)[\w\\/.\- ]{3,}|/(?:home|Users|srv|opt|var|mnt)/[\w/.\-]{3,}",
        "build paths carry your username, your employer and your directory layout",
    ),
    (
        "private-import",
        r"^[ \t]*import\s+(?:com|org|net|io)\.(?!"
        + "|".join(
            [
                "springframework",
                "junit",
                "slf4j",
                "fasterxml",
                "apache",
                "google",
                "jetbrains",
                "squareup",
                "netty",
                "hibernate",
                "mockito",
                "reactivex",
                "typesafe",
                "jsoup",
                "quarkus",
                "micronaut",
                "vertx",
                "grpc",
                "openjdk",
                "eclipse",
                "gradle",
                "sonatype",
                "yaml",
                "json",
                "w3c",
                "xml",
            ]
        )
        + r")[\w.]+",
        "an import of a group id nobody publishes is an import of your own code",
    ),
    (
        "internal-host",
        r"https?://[\w.\-]*\.(?:internal|local|corp|intranet|lan|test)\b[\w./\-]*",
        "internal hostnames map your network for anyone who cares",
    ),
    (
        "private-ip",
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
        "an RFC1918 address is an address inside your network",
    ),
    (
        "credential-literal",
        r"(?:api[_\-]?key|secret|password|passwd|token|access[_\-]?key)\s*[=:]\s*[\"'][^\"']{8,}",
        "a literal that looks like a credential, whether or not it is a live one",
    ),
    (
        "aws-access-key",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        "an AWS access key id",
    ),
    (
        "private-key-block",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "a private key, in full, in an image",
    ),
    (
        "jwt",
        r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}",
        "a JWT, which usually decodes to a real account",
    ),
    (
        "connection-string",
        r"\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s\"']*:[^\s\"'@]+@[^\s\"']+",
        "a database URL with credentials in it",
    ),
)


@dataclass(frozen=True)
class GuardRule:
    """One named check."""

    name: str
    pattern: Pattern[str]
    why: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GuardRule":
        if "name" not in data or "pattern" not in data:
            raise ConfigError("guard rule needs a 'name' and a 'pattern'")
        flags = re.M
        if data.get("ignore_case", False):
            flags |= re.I
        try:
            pattern = re.compile(str(data["pattern"]), flags)
        except re.error as exc:
            raise ConfigError(f"guard rule {data['name']!r}: bad regex ({exc})") from exc
        return cls(name=str(data["name"]), pattern=pattern, why=str(data.get("why", "")))


@dataclass(frozen=True)
class Finding:
    """One thing the guard would rather you did not publish."""

    rule: str
    match: str
    line: int
    why: str = ""

    def __str__(self) -> str:
        return f"line {self.line}: {self.rule}: {self.match}"


class LeakDetected(Exception):
    """Raised instead of rendering, when the guard is in ``error`` mode."""

    def __init__(self, findings: Sequence[Finding]):
        self.findings: Tuple[Finding, ...] = tuple(findings)
        listing = "; ".join(str(f) for f in self.findings)
        super().__init__(f"snippet identifies a codebase ({listing})")


def default_rules() -> List[GuardRule]:
    """The rules codecard ships with. A fresh list, so callers can edit it."""
    return [
        GuardRule(name=name, pattern=re.compile(pattern, re.M | re.I), why=why)
        for name, pattern, why in _DEFAULT_RULE_SOURCE
    ]


@dataclass
class Guard:
    """A configured set of rules plus what to do when one of them fires."""

    mode: str = "error"
    rules: List[GuardRule] = field(default_factory=default_rules)
    allow: List[Pattern[str]] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    def scan(self, text: str) -> List[Finding]:
        """Every match, with the 1-based line it sits on. Never raises."""
        if not self.enabled:
            return []
        findings: List[Finding] = []
        for rule in self.rules:
            for m in rule.pattern.finditer(text):
                sample = m.group(0).strip()
                if any(a.search(sample) for a in self.allow):
                    continue
                findings.append(
                    Finding(
                        rule=rule.name,
                        match=sample[:80],
                        line=text.count("\n", 0, m.start()) + 1,
                        why=rule.why,
                    )
                )
        findings.sort(key=lambda f: (f.line, f.rule))
        return findings

    def check(self, text: str) -> List[Finding]:
        """Scan, and raise :class:`LeakDetected` if the mode says to stop."""
        findings = self.scan(text)
        if findings and self.mode == "error":
            raise LeakDetected(findings)
        return findings

    @classmethod
    def from_config(cls, data: Any) -> "Guard":
        """Build a guard from the ``guard:`` block of a config file.

        Accepts a bool, a mode string, or a mapping::

            guard:
              mode: warn            # error | warn | off
              disable: [absolute-path]
              only: [credential-literal]     # optional whitelist of rules to run
              allow: ["https://example\\.com"]
              rules:
                - name: ticket-id
                  pattern: "[A-Z]{2,}-[0-9]+"
                  why: our tracker ids are not public
        """
        if data is None:
            return cls()
        if isinstance(data, bool):
            return cls(mode="error" if data else "off")
        if isinstance(data, str):
            return cls(mode=normalize_mode(data))
        if not isinstance(data, Mapping):
            raise ConfigError(f"guard: expected a mapping, got {type(data).__name__}")

        unknown = set(data) - {"mode", "enabled", "disable", "only", "allow", "rules"}
        if unknown:
            raise ConfigError(f"guard: unknown key(s) {sorted(unknown)}")

        mode = "error"
        if "enabled" in data:
            mode = "error" if data["enabled"] else "off"
        if "mode" in data:
            mode = normalize_mode(str(data["mode"]))

        rules = default_rules()
        only = data.get("only")
        if only:
            wanted = {str(x) for x in only}
            _warn_unknown_rule_names(wanted, rules, "only")
            rules = [r for r in rules if r.name in wanted]
        disable = data.get("disable") or []
        if disable:
            dropped = {str(x) for x in disable}
            _warn_unknown_rule_names(dropped, rules, "disable")
            rules = [r for r in rules if r.name not in dropped]
        for extra in data.get("rules") or []:
            rules.append(GuardRule.from_dict(extra))

        allow: List[Pattern[str]] = []
        for pattern in data.get("allow") or []:
            try:
                allow.append(re.compile(str(pattern)))
            except re.error as exc:
                raise ConfigError(f"guard.allow: bad regex {pattern!r} ({exc})") from exc

        return cls(mode=mode, rules=rules, allow=allow)


def normalize_mode(value: str) -> str:
    """``on``/``true``/``strict`` mean ``error``; ``false``/``no`` mean ``off``."""
    v = value.strip().lower()
    if v in ("error", "strict", "on", "true", "yes", "1"):
        return "error"
    if v in ("warn", "warning"):
        return "warn"
    if v in ("off", "false", "no", "0", "none"):
        return "off"
    raise ConfigError(f"guard mode: expected one of {MODES}, got {value!r}")


def _warn_unknown_rule_names(names: Iterable[str], rules: Sequence[GuardRule], key: str) -> None:
    known = {r.name for r in rules}
    missing = sorted(set(names) - known)
    if missing:
        raise ConfigError(
            f"guard.{key}: no such rule(s) {missing}. Known rules: {sorted(known)}"
        )


def scan(text: str, guard: Optional[Guard] = None) -> List[Finding]:
    """Convenience: scan a string with the default rules."""
    return (guard or Guard()).scan(text)


def rule_table() -> Dict[str, str]:
    """``{name: why}`` for the built-in rules, used by ``codecard --list-rules``."""
    return {name: why for name, _pattern, why in _DEFAULT_RULE_SOURCE}
