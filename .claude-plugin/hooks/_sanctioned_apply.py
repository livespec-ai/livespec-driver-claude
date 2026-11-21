#!/usr/bin/env python3
"""
The sanctioned deploy path: `just ansible-apply|ansible-drift` and `ansible-playbook`.

The discipline's positive statement is "a deploy is a git change plus the
committed apply, run from the control node over committed source". This module
recognises that apply so `_host_mutation` can let it through — and recognises
the one shape of it that is NOT the discipline: a playbook that positively is
not committed source.

  - The sanction applies only when the sanctioned head is the segment's FIRST
    recognised command head. A path operand that happens to be named
    `ansible`, or a trailing `ansible` word after a mutating `ssh`, sanctions
    nothing; bare `ansible` (ad hoc) is not sanctioned at all and is judged
    by `_mutation_verbs` like any other head.
  - `ansible-playbook <playbook>` / `just ansible-apply <playbook>` is a hand
    deploy when the playbook is positively outside committed source: under
    `/tmp`, `/var/tmp`, `/dev/shm`, or an unrecognised home-relative path, or
    carrying `..` or a `$`. The fleet's `~/workspace/<checkout>/` and
    `~/.worktrees/<repo>/<branch>/` layouts name committed source just as an
    absolute checkout path does, so they pass. Option values (`-i
    <inventory>`, `-e <vars>`, `--vault-password-file <file>`, …) are never
    playbooks, and neither is a redirect target: `… > $L 2>&1` writes a LOG,
    so reading `$L` as a second playbook convicts the log file and refuses the
    sanctioned apply (work-item livespec-driver-claude-q2urvj).
  - `--check` (and `just ansible-drift`, which IS `--check --diff`) reads.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import re
import shlex

from _shell_lex import basename, without_redirections

__all__: list[str] = ["remember_literals", "sanction"]

_SANCTIONED_RECIPES = frozenset({"ansible-apply", "ansible-drift"})
# ansible-playbook options whose value is not a playbook.
_PLAYBOOK_VALUE_FLAGS = frozenset(
    "-i --inventory --inventory-file -e --extra-vars --vault-password-file --vault-id -l "
    "--limit -t --tags --skip-tags -u --user -c --connection -T --timeout --private-key "
    "--key-file -M --module-path --become-user --become-method -f --forks --ssh-common-args "
    "--ssh-extra-args --scp-extra-args --sftp-extra-args --start-at-task".split()
)
_UNCOMMITTED_PREFIXES = ("/tmp", "/var/tmp", "/dev/shm")
_HOME_CHECKOUT = re.compile(r"^~/(?:workspace/[^/]+/.+|\.worktrees/[^/]+/[^/]+/.+)")
_ASSIGNMENT_WORD = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$")
_VARIABLE_WORD = re.compile(r"^\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})$")
_NON_LITERAL_VALUE = re.compile(r"[$\x60*?\[\\|&;<>]")


def remember_literals(*, tokens: list[str], variables: dict[str, list[str]]) -> None:
    """Remember only assignment-only segments whose values are literal argv."""
    assignments = [_ASSIGNMENT_WORD.match(token) for token in tokens]
    if not assignments or any(assignment is None for assignment in assignments):
        return
    for assignment in assignments:
        assert assignment is not None
        name, value = assignment.group("name"), assignment.group("value")
        if _NON_LITERAL_VALUE.search(value):
            _ = variables.pop(name, None)
            continue
        try:
            variables[name] = shlex.split(value, posix=True)
        except ValueError:
            _ = variables.pop(name, None)


def _expanded(*, tokens: list[str], variables: dict[str, list[str]]) -> list[str]:
    """Expand whole-word literal variables after a sanctioned head is known.

    Unresolved variables remain intact, so the playbook classifier refuses
    them rather than treating process-environment state as committed source.
    """
    result: list[str] = []
    for token in tokens:
        match = _VARIABLE_WORD.match(token)
        if match:
            name = match.group(1) or match.group(2)
            result.extend(variables.get(name, [token]))
        else:
            result.append(token)
    return result


def _outside_committed_source(*, playbook: str) -> bool:
    """Whether a path is positively outside a source checkout.

    Home-relative paths are normally scratch paths, except the two checkout
    layouts the fleet uses. They name committed source just as an absolute
    checkout path does; a bare ``~/play.yml`` remains scratch.
    """
    return (
        playbook.startswith(_UNCOMMITTED_PREFIXES)
        or (playbook.startswith("~") and _HOME_CHECKOUT.match(playbook) is None)
        or ".." in playbook
        or "$" in playbook
    )


def _playbook_rule(*, head: str, arguments: list[str]) -> str | None:
    """A playbook positively outside committed source is a hand deploy; `--check` reads."""
    arguments = without_redirections(tokens=arguments)
    if "--check" in arguments:
        return None
    playbooks: list[str] = []
    skip = False
    for argument in arguments:
        if skip or argument.startswith("-"):
            skip = argument in _PLAYBOOK_VALUE_FLAGS
            continue
        playbooks.append(argument)
    if any(_outside_committed_source(playbook=p) for p in playbooks):
        return f"{head}+uncommitted-playbook"
    return None


def sanction(
    *, tokens: list[str], known_heads: frozenset[str], variables: dict[str, list[str]]
) -> tuple[bool, str | None]:
    """(sanctioned, rule), judged on the segment's FIRST known command head only.

    `known_heads` is the caller's set of heads it recognises; the walk stops at
    the first of them, so a sanctioned head found AFTER an `ssh` sanctions
    nothing.
    """
    for index, token in enumerate(tokens):
        head = basename(token=token).lower()
        if head == "ansible-playbook":
            return True, _playbook_rule(
                head=head, arguments=_expanded(tokens=tokens[index + 1 :], variables=variables)
            )
        if head == "just" and index + 1 < len(tokens) and tokens[index + 1] in _SANCTIONED_RECIPES:
            recipe = tokens[index + 1]
            if recipe == "ansible-drift":
                return True, None
            return True, _playbook_rule(
                head=recipe, arguments=_expanded(tokens=tokens[index + 2 :], variables=variables)
            )
        if head in known_heads:
            return False, None
    return False, None
