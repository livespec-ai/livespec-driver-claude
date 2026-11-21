"""`_host_escape.verify_escape`: the audited escape must leave a ledger record.

The valve is audited only if the named work item EXISTS, is not closed, and
carries a `HOST-GUARD-ESCAPE` comment recorded before the command ran. When the
ledger itself is unreachable the verdict is `unverified` (never a deny), so the
guard can not deadlock a session. `bd` is faked; nothing here touches a ledger.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
_MARKER = "HOST-GUARD-ESCAPE: command=`git pull` reason=stale checkout backfill-due=2026-11-21"


def _verify(
    *, show: object, comments: object, calls: list[dict[str, object]] | None = None
) -> tuple[str, str]:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    module = importlib.import_module("_host_escape")

    def fake_run(args: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        if calls is not None:
            calls.append({"args": args, **kw})
        reply = show if "show" in args else comments
        if isinstance(reply, BaseException):
            raise reply
        assert isinstance(reply, subprocess.CompletedProcess)
        return reply

    return module.verify_escape(item_id="demo-abc123", project_dir="/nonexistent", run=fake_run)


def _ok(*, payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


_OPEN = _ok(payload=[{"id": "demo-abc123", "status": "active"}])
_RECORDED = _ok(payload=[{"text": _MARKER}])


def test_recorded_open_item_is_ok() -> None:
    assert _verify(show=_OPEN, comments=_RECORDED)[0] == "ok"


def test_missing_item_is_refused() -> None:
    gone = subprocess.CompletedProcess([], 1, stdout="", stderr="Error: issue not found")
    verdict, reason = _verify(show=gone, comments=_RECORDED)
    assert verdict == "refuse"
    assert "not found" in reason


def test_closed_item_is_refused() -> None:
    closed = _ok(payload=[{"id": "demo-abc123", "status": "closed"}])
    verdict, reason = _verify(show=closed, comments=_RECORDED)
    assert verdict == "refuse"
    assert "closed" in reason


def test_item_without_recorded_escape_is_refused() -> None:
    verdict, reason = _verify(show=_OPEN, comments=_ok(payload=[{"text": "unrelated"}]))
    assert verdict == "refuse"
    assert "HOST-GUARD-ESCAPE" in reason


@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError("bd"), subprocess.TimeoutExpired(cmd="bd", timeout=10)],
)
def test_unreachable_ledger_is_unverified_never_refused(failure: BaseException) -> None:
    assert _verify(show=failure, comments=failure)[0] == "unverified"


def test_ledger_outage_error_is_unverified() -> None:
    outage = subprocess.CompletedProcess([], 1, stdout="", stderr="Error 1045 Access denied")
    assert _verify(show=outage, comments=outage)[0] == "unverified"


def test_credential_failure_is_a_distinct_unverified_reason() -> None:
    denied = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="Error 1045 (28000): Access denied"
    )
    verdict, reason = _verify(show=denied, comments=denied)
    assert (verdict, reason) == ("unverified", "ledger-credential-failure")


def test_wrapper_500_is_a_distinct_unverified_reason() -> None:
    boom = subprocess.CompletedProcess([], 1, stdout="", stderr="(500) Internal Server Error")
    assert _verify(show=boom, comments=boom) == ("unverified", "wrapper-500")


@pytest.mark.parametrize(
    ("item_id", "directory", "prefix"),
    [
        ("other-abc123.2", "other-repo", "other"),
        ("overseer-x1y2z3", "livespec-overseer", "overseer"),
        ("bd-ib-q9w8e7", "livespec-orchestrator-beads-fabro", "bd-ib"),
    ],
)
def test_bd_runs_through_the_credential_wrapper_in_the_items_tenant(
    tmp_path: Path, item_id: str, directory: str, prefix: str
) -> None:
    for name, declared in (
        (directory, prefix),
        ("decoy", "livespec-dev-tooling"),
        ("short", "bd"),
    ):
        (tmp_path / name / ".beads").mkdir(parents=True)
        (tmp_path / name / ".beads" / "config.yaml").write_text(
            f"# comment\ndolt.prefix: {declared}\n", encoding="utf-8"
        )
    calls: list[dict[str, object]] = []
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    module = importlib.import_module("_host_escape")

    def fake_run(args: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kw})
        return _OPEN if "show" in args else _RECORDED

    module.verify_escape(
        item_id=item_id,
        project_dir="/nonexistent",
        run=fake_run,
        workspace_root=str(tmp_path),
    )
    assert calls
    for call in calls:
        assert call["args"][:2] == ["/usr/local/bin/with-livespec-env.sh", "--"]
        assert call["cwd"] == str(tmp_path / directory)


def test_single_object_show_reply_is_read_like_a_list() -> None:
    closed = _ok(payload={"id": "demo-abc123", "status": "closed"})
    assert _verify(show=closed, comments=_RECORDED)[0] == "refuse"
