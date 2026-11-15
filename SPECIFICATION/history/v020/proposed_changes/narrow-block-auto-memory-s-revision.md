---
proposal: narrow-block-auto-memory-s.md
decision: accept
revised_at: 2026-11-15T16:23:19Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted as filed under delegated decision mode. legacy-coordinator-agent graded livespec-driver-claude#1106 PASS at 434d8ab, after one re-anchor nit. The block_auto_memory file-tool route narrows from any **/memory/*.md to a *.md directly under projects/<slug>/memory/ (plus the Codex store unchanged), which matches the hook's own Bash classifier and livespec-dev-tooling's vendored managed copy (#4762, pik7f2). A tracked <repo>/.ai/memory/<topic>.md, where durable guidance belongs, is no longer refused. The new scenario proves both halves in one session. Carried for implementation by livespec-driver-claude-chg7cf. No design record is contradicted.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-15T16:23:15Z
verdict: NO BLOCKERS
proposal_stem: narrow-block-auto-memory-s
content_digest: f774df92ce4ee625c1444393a287d95392662277dc661023345f495c4a69b30d
