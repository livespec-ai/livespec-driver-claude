"""Ledger verification of the fleet_host_guard audited escape.

The escape is audited only if the work item named by
`LIVESPEC_HOST_GUARD_ESCAPE=<id>` EXISTS, is not closed, and carries a
`HOST-GUARD-ESCAPE:` comment (exact command, reason, `backfill-due=<date>`)
recorded BEFORE the command ran. A tick finds owed backfills by grepping the
ledger for that marker.

`bd` runs through the credential wrapper, in the checkout of the item's OWN
tenant (resolved from the id prefix), never the cwd's. When the ledger can not
answer, the verdict is `unverified` with a distinct reason and the escape is
still allowed: the guard must never deadlock a session. Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

__all__: list[str] = ["verify_escape"]

_WRAPPER = "/usr/local/bin/with-livespec-env.sh"
_MARKER = "HOST-GUARD-ESCAPE"
_LABEL = "host-guard-escape"
_TIMEOUT_SECONDS = 15
_PREFIX_LINE = re.compile(r"^dolt\.prefix:\s*([A-Za-z0-9._-]+)\s*$", re.MULTILINE)
_DEFAULT_ROOTS = (Path("~/workspace"), Path("/data/projects"))
_Run = Callable[..., "subprocess.CompletedProcess[str]"]


def _declared_prefix(*, checkout: Path) -> str | None:
    """The issue prefix a checkout's `.beads/config.yaml` declares (`dolt.prefix`)."""
    try:
        text = (checkout / ".beads" / "config.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = _PREFIX_LINE.search(text)
    return match.group(1) if match else None


def _tenant_dir(*, item_id: str, project_dir: str, workspace_root: str) -> str:
    """The checkout whose declared prefix owns `item_id`; longest prefix wins.

    The id prefix is NOT the directory name (`overseer-` lives in
    `livespec-overseer`, `bd-ib-` in `livespec-orchestrator-beads-fabro`), so it is
    read from each checkout's own declaration. Roots cover a workstation
    (`~/workspace`) and the vps (`/data/projects`).
    """
    roots = [Path(workspace_root)] if workspace_root else list(_DEFAULT_ROOTS)
    best_len = 0
    best = project_dir
    for root in roots:
        try:
            checkouts = sorted(root.expanduser().iterdir())
        except OSError:
            continue
        for checkout in checkouts:
            prefix = _declared_prefix(checkout=checkout)
            if prefix and item_id.startswith(prefix + "-") and len(prefix) > best_len:
                best_len = len(prefix)
                best = str(checkout)
    return best


def _failure_reason(*, stderr: str) -> str:
    if "1045" in stderr:
        return "ledger-credential-failure"
    if "500" in stderr and "Internal Server Error" in stderr:
        return "wrapper-500"
    return "ledger-unreachable"


def _bd(*, run: _Run, args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return run(
        [_WRAPPER, "--", "bd", *args],
        cwd=cwd or None,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT_SECONDS,
    )


def _records(*, raw: str) -> list[dict[str, object]]:
    value: object = json.loads(raw)
    entries: list[object] = []
    if isinstance(value, dict):
        entries = [value]
    elif isinstance(value, list):
        entries = cast("list[object]", value)
    return [cast("dict[str, object]", entry) for entry in entries if isinstance(entry, dict)]


def _label(*, run: _Run, item_id: str, cwd: str) -> str:
    """Label the item so the audit report finds it; a failure is a reason, never a refusal."""
    try:
        done = _bd(run=run, args=["label", "add", item_id, _LABEL], cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return "label-failed"
    return "" if done.returncode == 0 else "label-failed"


def verify_escape(
    *,
    item_id: str,
    project_dir: str,
    run: _Run | None = None,
    workspace_root: str = "",
) -> tuple[str, str]:
    """Return `(verdict, reason)`: `ok`, `refuse`, or `unverified`."""
    runner = run or subprocess.run
    cwd = _tenant_dir(item_id=item_id, project_dir=project_dir, workspace_root=workspace_root)
    try:
        shown = _bd(run=runner, args=["show", item_id, "--json"], cwd=cwd)
        if shown.returncode != 0:
            text = shown.stderr + shown.stdout
            if "not found" in text.lower() or "no issue" in text.lower():
                return ("refuse", f"work item {item_id} was not found in its ledger")
            return ("unverified", _failure_reason(stderr=text))
        items = _records(raw=shown.stdout)
        if items and items[0].get("status") == "closed":
            return ("refuse", f"work item {item_id} is closed")
        noted = _bd(run=runner, args=["comments", item_id, "--json"], cwd=cwd)
        if noted.returncode != 0:
            return ("unverified", _failure_reason(stderr=noted.stderr + noted.stdout))
        for comment in _records(raw=noted.stdout):
            if _MARKER in str(comment.get("text") or comment.get("body") or ""):
                return ("ok", _label(run=runner, item_id=item_id, cwd=cwd))
    except (OSError, subprocess.SubprocessError, ValueError):
        return ("unverified", "ledger-unreachable")
    return ("refuse", f"work item {item_id} has no {_MARKER} comment recording the command")
