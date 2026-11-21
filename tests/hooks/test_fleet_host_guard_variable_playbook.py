"""A literal shell-variable playbook operand expands before the guard judges it.

The guard reads the complete shell command, so an assignment of a literal,
in-tree playbook before `just ansible-apply $A` can be expanded safely. This
lets the committed route through without using the escape valve (plan
fleet-host-guard-escape-valve, livespec-dev-tooling-twdyzy).

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
# The recorded tool call, whose literal in-tree assignment is safe to expand.
_LITERAL_ASSIGNMENT = (
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


def test_literal_variable_playbook_path_is_allowed() -> None:
    assert _run(command=_LITERAL_ASSIGNMENT) == ""


def test_literal_playbook_path_is_allowed() -> None:
    assert _run(command=_LITERAL) == ""
