#!/usr/bin/env bash
# Deliberately omit errexit so the advisory green-token probe can fall through
# to the full aggregate when it misses. CI remains authoritative.
set -uo pipefail

# Advisory-local green-token short-circuit: if the current HEAD tree was
# already verified clean by a successful full `just check` run, skip the
# full aggregate. The token is invalidated by any new commit (tree-hash
# change) or an uncommitted worktree modification. STRICTLY advisory-local;
# CI is authoritative -- a token match never bypasses the remote gate.
if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
    # A token match no longer skips the aggregate: the token memoizes a tree, and members that read
    # state outside the tree (master CI, branch protection, the ledger, the workflow-edit exemption)
    # can answer differently for the same tree, so a refused or partial earlier run must not
    # stand in for this push (livespec-dev-tooling-mj37jk; dev-tooling fdd0ea878).
    echo ":: pre-push: green token matched - NOT skipping the aggregate; members that read state outside the tree must run on this push"
fi

# Delegated gate: `enabled` is true only when this repository opts in AND this
# host can read the gates kubeconfig. `exec` is load-bearing -- a delegated run
# that reaches no verdict must refuse the push, never fall through to the local
# aggregate. A host that cannot delegate (a Fabro sandbox) gets a non-zero
# `enabled`, which reports that it gates locally, and runs `just check` below.
if uv run python -m livespec_dev_tooling.gate_remote_delegate enabled; then
    echo ":: pre-push: delegating the gate to the remote executor"
    exec uv run python -m livespec_dev_tooling.gate_remote_delegate run
fi

just check
