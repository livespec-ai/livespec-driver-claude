"""Hook-boundary coverage for kubectl wrappers accepted by fleet_host_guard."""

from __future__ import annotations

import importlib
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
_WRAPPER = "homelab-worker/remote-kubectl.sh"


def _load_hook() -> ModuleType:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("fleet_host_guard", None)
    return importlib.import_module("fleet_host_guard")


def _run(*, command: str) -> str:
    old_stdin = sys.stdin
    stdout = StringIO()
    stderr = StringIO()
    try:
        sys.stdin = StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            assert _load_hook().main() == 0, stderr.getvalue()
    finally:
        sys.stdin = old_stdin
    assert stderr.getvalue() == ""
    return stdout.getvalue()


@pytest.mark.parametrize(
    "verb",
    ["uncordon", "drain", "taint", "label", "annotate", "patch", "delete", "apply", "edit"],
)
def test_denies_each_mutating_kubectl_wrapper_verb(verb: str) -> None:
    output = _run(command=f"{_WRAPPER} {verb} node")

    reason = json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]
    assert f"(kubectl+{verb})" in reason


@pytest.mark.parametrize("verb", ["get", "describe", "logs", "wait"])
def test_allows_read_only_kubectl_wrapper_verbs(verb: str) -> None:
    assert _run(command=f"{_WRAPPER} {verb} nodes") == ""
