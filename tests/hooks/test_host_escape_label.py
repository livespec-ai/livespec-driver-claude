"""An allowed escape labels its work item `host-guard-escape`, so the audit report finds it.

livespec-dev-tooling `scripts/coordinator/host-guard-backfills` lists escapes by that label. A
seat that forgets the label would be invisible to the audit, so the HOOK applies it at allow time. A
labelling failure never refuses the escape: it only changes the reason. `bd` is faked.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
_MARKER = "HOST-GUARD-ESCAPE: command=x reason=y backfill-due=2026-11-22"


def _ok(*, payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


def _verify(
    *, label_rc: int, status: str = "active", comments: object = None
) -> tuple[tuple[str, str], list[list[str]]]:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    module = importlib.import_module("_host_escape")
    calls: list[list[str]] = []
    recorded = [{"text": _MARKER}] if comments is None else comments

    def fake_run(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if "label" in args:
            return subprocess.CompletedProcess(args, label_rc, stdout="", stderr="boom")
        if "show" in args:
            return _ok(payload=[{"id": "demo-abc123", "status": status}])
        return _ok(payload=recorded)

    verdict = module.verify_escape(item_id="demo-abc123", project_dir="/nonexistent", run=fake_run)
    return verdict, calls


def test_allowed_escape_labels_its_item_through_the_wrapper() -> None:
    verdict, calls = _verify(label_rc=0)
    assert verdict == ("ok", "")
    labelled = [c for c in calls if "label" in c]
    assert labelled
    assert labelled[0][:3] == ["/usr/local/bin/with-livespec-env.sh", "--", "bd"]
    assert labelled[0][3:] == ["label", "add", "demo-abc123", "host-guard-escape"]


def test_label_failure_never_refuses_the_escape() -> None:
    verdict, _calls = _verify(label_rc=1)
    assert verdict == ("ok", "label-failed")


def test_refused_escape_is_not_labelled() -> None:
    verdict, calls = _verify(label_rc=0, status="closed")
    assert verdict[0] == "refuse"
    assert not [c for c in calls if "label" in c]
