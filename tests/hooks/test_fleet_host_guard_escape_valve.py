"""Escape valve for `fleet_host_guard` (plan fleet-host-guard-escape-valve).

The guard must never deadlock a session: an AUDITED escape names a ledger
work item in the command itself, and the stale-checkout bootstrap class
(`git pull --ff-only`, `git fetch`) over ssh is allowed outright.

Every command below is INERT DATA fed to the hook on stdin.
"""

from __future__ import annotations

import importlib
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
_MUTATION = "sudo systemctl restart k3s"


def _run(*, command: str) -> str:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("fleet_host_guard", None)
    hook = importlib.import_module("fleet_host_guard")
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    old = sys.stdin
    out = StringIO()
    try:
        sys.stdin = StringIO(stdin)
        with redirect_stdout(out):
            assert hook.main() == 0
    finally:
        sys.stdin = old
    return out.getvalue()


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setenv("LIVESPEC_SANDBOX_OTEL_ENDPOINT", "http://127.0.0.1:9")
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    escape = importlib.import_module("_host_escape")
    monkeypatch.setattr(escape, "verify_escape", lambda **_kw: ("ok", ""))


def test_unaudited_mutation_is_denied_and_reason_names_the_valve() -> None:
    out = _run(command=f"ssh poweredge-xubuntu '{_MUTATION}'")
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "LIVESPEC_HOST_GUARD_ESCAPE=<work-item-id>" in reason


def test_audited_escape_with_ledger_id_is_allowed() -> None:
    escape = "LIVESPEC_HOST_GUARD_ESCAPE=livespec-dev-tooling-twdyzy"
    cmd = f"{escape} ssh poweredge-xubuntu '{_MUTATION}'"
    assert _run(command=cmd) == ""


def test_escape_without_a_work_item_id_is_still_denied() -> None:
    cmd = f"LIVESPEC_HOST_GUARD_ESCAPE= ssh poweredge-xubuntu '{_MUTATION}'"
    assert _run(command=cmd) != ""


@pytest.mark.parametrize(
    "remote", ["git -C ~/workspace/livespec-dev-tooling pull --ff-only", "git fetch origin"]
)
def test_stale_checkout_bootstrap_is_allowed_outright(remote: str) -> None:
    assert _run(command=f"ssh poweredge-xubuntu '{remote}'") == ""


def test_escape_naming_an_unrecorded_item_is_denied_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    escape = importlib.import_module("_host_escape")
    monkeypatch.setattr(escape, "verify_escape", lambda **_kw: ("refuse", "item is closed"))
    cmd = f"LIVESPEC_HOST_GUARD_ESCAPE=demo-abc123 ssh poweredge-xubuntu '{_MUTATION}'"
    reason = json.loads(_run(command=cmd))["hookSpecificOutput"]["permissionDecisionReason"]
    assert "item is closed" in reason


def test_unverified_ledger_still_allows_the_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    escape = importlib.import_module("_host_escape")
    monkeypatch.setattr(
        escape, "verify_escape", lambda **_kw: ("unverified", "ledger-credential-failure")
    )
    cmd = f"LIVESPEC_HOST_GUARD_ESCAPE=demo-abc123 ssh poweredge-xubuntu '{_MUTATION}'"
    assert _run(command=cmd) == ""


def test_deny_reason_tells_the_session_what_to_record_on_the_ledger() -> None:
    out = _run(command=f"ssh poweredge-xubuntu '{_MUTATION}'")
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "HOST-GUARD-ESCAPE: command=" in reason
    assert "backfill-due=" in reason
