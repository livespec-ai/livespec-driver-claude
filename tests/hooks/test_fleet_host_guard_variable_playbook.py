"""A shell-variable playbook operand is refused with a message that names the cause.

The guard reads command text and cannot expand `$A`, so `just ansible-apply $A`
is judged uncommitted. The refusal must say so and tell the session to write
the committed playbook path literally, so one retry fixes it instead of the
escape valve (plan fleet-host-guard-escape-valve, livespec-dev-tooling-twdyzy).

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
# The refused tool call, as recorded from the gate-job-resources seat.
_REFUSED = (
    "cd /home/ubuntu/workspace/livespec-dev-tooling && S=/tmp/scratch; "
    'A="ansible/k3s-window-drain.yml -e k3s_window_action=uncordon '
    "-e k3s_window_confirm=uncordon -e k3s_window_node=gamingpc-xubuntu "
    '-e k3s_window_node_confirm=gamingpc-xubuntu"; '
    "mise exec -- just ansible-apply $A > $S/unc-apply.log 2>&1"
)
_LITERAL = (
    "just ansible-apply ansible/k3s-window-drain.yml "
    "-e k3s_window_action=uncordon > /tmp/unc.log 2>&1"
)


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


def test_variable_playbook_refusal_names_the_cause_and_the_fix() -> None:
    reason = json.loads(_run(command=_REFUSED))["hookSpecificOutput"]["permissionDecisionReason"]
    assert "uncommitted-playbook" in reason
    assert "shell variable" in reason
    assert "write the committed playbook path literally" in reason


def test_literal_playbook_path_is_allowed() -> None:
    assert _run(command=_LITERAL) == ""
