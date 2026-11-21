"""Literal command-head and ledger-data recognition for the host-mutation guard."""

from __future__ import annotations

import re

from _remote_target import is_fleet_host, parse_sftp, sftp_batch_mutates
from _shell_io import DATA_HEADS
from _shell_lex import SHELL_KEYWORDS_DATA, SHELL_KEYWORDS_PASS, basename, first_command_index

__all__: list[str] = [
    "cluster_command",
    "command_start",
    "is_ledger_write",
    "literal_bindings",
    "opens_case",
    "resolved_head",
    "sftp_rule",
    "unreadable_stdin_file",
]

_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_VARIABLE_HEAD = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")


def literal_bindings(
    *, bindings: tuple[tuple[str, str], ...], tokens: list[str]
) -> tuple[tuple[str, str], ...]:
    """Keep literal path assignments that can safely resolve a later `$NAME` head."""
    resolved = dict(bindings)
    for token in tokens:
        assignment = _ASSIGNMENT.match(token)
        if assignment is None:
            break
        name, value = assignment.groups()
        if "$" in value or "`" in value or "{}" in value or "/" not in value:
            _ = resolved.pop(name, None)
        else:
            resolved[name] = value
    return tuple(resolved.items())


def resolved_head(*, token: str, bindings: tuple[tuple[str, str], ...]) -> str:
    """Return a provably literal variable command head, otherwise ``token``."""
    variable = _VARIABLE_HEAD.match(token)
    return dict(bindings).get(variable.group(1), token) if variable else token


def is_ledger_write(
    *,
    seg: str,
    tokens: list[str] | None,
    command_index: int | None,
    bindings: tuple[tuple[str, str], ...],
) -> bool:
    """Whether ``seg`` is a `bd` ledger write whose operands are data.

    The prefix intentionally suffices when an escape-heavy quoted comment body
    cannot be lexed: it remains data passed to `bd`, never shell to execute. A
    `$NAME` wrapper head only qualifies when ``bindings`` proves it a literal path.
    """
    if tokens is not None and command_index is not None:
        resolved = resolved_head(token=tokens[command_index], bindings=bindings)
        head = resolved.rsplit("/", 1)[-1].lower()
        rest = tokens[command_index + 1 :]
        if head == "bd":
            return bool(rest) and (rest[0] == "comment" or rest[:2] == ["comments", "add"])
        if head == "with-livespec-env.sh" and len(rest) > 2 and rest[:2] == ["--", "bd"]:
            return rest[2] == "comment" or rest[2:4] == ["comments", "add"]

    prefix = seg.lstrip()
    wrapper = (
        r"(?:\$(?P<variable>[A-Za-z_][A-Za-z0-9_]*)"
        r"|(?:[^\s;/]+/)?with-livespec-env\.sh)\s+--\s+"
    )
    matched = re.match(
        rf"(?:{wrapper})?bd\s+(?:comment\b|comments\s+add\b)", prefix, flags=re.IGNORECASE
    )
    if matched is None:
        return False
    variable = matched.group("variable")
    return variable is None or variable in dict(bindings)


def cluster_command(*, head: str, cluster_heads: frozenset[str]) -> str | None:
    """The cluster tool a command head represents, including kubectl wrappers."""
    return "kubectl" if "kubectl" in head else head if head in cluster_heads else None


def unreadable_stdin_file(*, tokens: list[str]) -> bool:
    """Whether stdin comes from a local file the hook cannot inspect."""
    return any(re.match(r"^(?:0)?<(?![<&])", token) is not None for token in tokens)


def sftp_rule(
    *, arguments: list[str], stdin: str | None, hosts: frozenset[str], hinted: bool
) -> str | None:
    """Does `sftp` reach a fleet host — or an unreadable one — with a write?"""
    sftp = parse_sftp(arguments=arguments)
    batch = stdin if sftp.batch_from_stdin else None
    mutates = batch is not None and sftp_batch_mutates(batch=batch)
    if sftp.unresolvable:
        return None if not hinted or (batch is not None and not mutates) else "unresolvable-target"
    if sftp.host is None or not is_fleet_host(name=sftp.host, hosts=hosts):
        return None
    return "sftp+batch" if mutates else None


def opens_case(*, tokens: list[str]) -> bool:
    """Whether one segment begins the shell's one-line `case` form."""
    start = first_command_index(tokens=tokens)
    return start is not None and tokens[start].lower() == "case"


def command_start(*, seg: str, tokens: list[str]) -> int | None:
    """Locate a command after assignments, keywords, and an optional case pattern."""
    start = first_command_index(tokens=tokens)
    if start is None:
        return None
    first_word = seg.split(None, 1)[0]
    if first_word.endswith(")") and not first_word.startswith("("):
        start += 1
    while start < len(tokens) and tokens[start].lower() in SHELL_KEYWORDS_PASS:
        start += 1
    if start >= len(tokens) or tokens[start].lower() in SHELL_KEYWORDS_DATA:
        return None
    return start if basename(token=tokens[start]).lower() not in DATA_HEADS else None
