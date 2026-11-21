"""Committed playbooks pass only when their shell operand is safely known."""

from __future__ import annotations

import sys
from pathlib import Path

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
_HOSTS = frozenset({"poweredge-xubuntu"})


def _classify(*, command: str) -> str | None:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    from _host_mutation import classify

    return classify(command=command, hosts=_HOSTS)


def test_committed_playbook_operands_are_allowed() -> None:
    for command in (
        'A="ansible/k3s-window-drain.yml -e k3s_window_action=cordon"; just ansible-apply $A',
        "just ansible-apply ~/workspace/livespec-dev-tooling/ansible/k3s-window-drain.yml",
        "just ansible-apply ~/.worktrees/livespec-dev-tooling/feature/ansible/k3s-window-drain.yml",
    ):
        assert _classify(command=command) is None


def test_unresolved_or_scratch_playbook_operands_are_refused() -> None:
    for command in (
        "just ansible-apply /tmp/play.yml",
        "just ansible-apply ~/play.yml",
        "PB=/tmp/play.yml; just ansible-apply $PB",
        "PB=$(printf ansible/k3s-window-drain.yml); just ansible-apply $PB",
        "just ansible-apply $PB",
    ):
        assert _classify(command=command) == "ansible-apply+uncommitted-playbook"
