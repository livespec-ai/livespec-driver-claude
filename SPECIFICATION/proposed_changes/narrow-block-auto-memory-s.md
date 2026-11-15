---
topic: narrow-block-auto-memory-s
author: claude-opus-5-5 (no-local-agent-memory seat)
created_at: 2026-11-15T15:02:36Z
---

## Proposal: block_auto_memory's file-tool route matches only the Claude Code projects/<slug>/memory layout

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Narrow the file-tool half of the auto-memory redirect from any `**/memory/*.md` to a `*.md` file directly under a `projects/<slug>/memory/` directory, which is the Claude Code auto-memory layout `~/.claude/projects/<slug>/memory/`, plus any file under the Codex store `~/.codex/memories/` as now. A tracked repository file whose parent directory merely happens to be named `memory`, such as `<repo>/.ai/memory/x.md`, is no longer refused. This matches the hook's own Bash classifier, which already requires `.claude/projects/<slug>/memory`, and the fleet managed copy that livespec-dev-tooling vendors.

### Motivation

Work item livespec-driver-claude-chg7cf was filed at spec-change tier with this topic. block_auto_memory.py's `_is_memory_file` refuses ANY `**/memory/*.md` (`target.parent.name == "memory"`). That is broader than the Claude Code layout and broader than the Bash route, so it refuses tracked repository guidance files such as `openclaw-info/.ai/memory/*.md`. Refusing them works against the fleet's own rule, which is to put durable guidance in tracked `.ai/` files. livespec-dev-tooling#4762 (livespec-dev-tooling-pik7f2) vendors this hook as fleet managed policy and already narrows its copy (parent named `memory`, great-grandparent named `projects`). legacy-coordinator-agent's grade on #4762 (2026-11-15) asked that the Driver's own matcher be narrowed the same way, so that a re-vendor does not bring the breadth back. Prose link: plan no-local-agent-memory (hetzner-xubuntu-info, epic hxi-7ituzy). The in-flight spec PR #1077 (tests-that-run-a-real) touches neither section, so default-align applies.

### Proposed Changes

In SPECIFICATION/contracts.md, in the bullet for the PreToolUse auto-memory redirect (`block_auto_memory.py`), replace

> directory — a file tool targeting `**/memory/*.md` or a file under
> `~/.codex/memories/`,

with

> directory — a file tool targeting a `*.md` file directly under a
> `projects/<slug>/memory/` directory (the Claude Code auto-memory layout
> `~/.claude/projects/<slug>/memory/`) or a file under
> `~/.codex/memories/`,

and append to that bullet, before "A no-op pass-through when the project is not livespec-governed;", the sentence: "The file-tool route MUST NOT refuse a write to a file whose parent directory is named `memory` but which is not directly under a `projects/<slug>/` directory, such as a tracked `<repo>/.ai/memory/<topic>.md`, because tracked `.ai/` files are where durable guidance belongs."

In SPECIFICATION/scenarios.md, in "## Scenario: auto-memory write in a governed project is intent-routed by the block-auto-memory hook", replace the line

`When an agent attempts Write, Edit or MultiEdit to a path matching **/memory/*.md`

with

`When an agent attempts Write, Edit or MultiEdit to a path matching **/projects/<slug>/memory/*.md`

and add the following scenario immediately after "## Scenario: reading or removing a memory note is not refused by the block-auto-memory hook":

## Scenario: a tracked .ai/memory file in a governed project is not refused by the block-auto-memory hook

```gherkin
Given a governed project whose .livespec.jsonc declares an implementation.plugin
When an agent attempts Write, Edit or MultiEdit to <project>/.ai/memory/x.md, a tracked file whose parent directory is named memory but is not under a projects/<slug>/ directory
Then the PreToolUse hook MUST let the write run
And a Write to ~/.claude/projects/<slug>/memory/x.md in the same session MUST still be blocked with the intent-routing reason
```

The revise that ratifies this MUST add a `tests/heading-coverage.json` row for the new scenario heading, owned by livespec-driver-claude-chg7cf, and MUST regenerate the debt register in the revise commit.
