# Phase 0 — Claude Documentation Handoff

**Date:** 2026-04-16
**Companion to:** `PHASE_0_STABILIZE_CHECKLIST_20260416.md`
**Audience:** Claude (planning/strategy lane) — what to do *after* Codex executes each phase

---

## How the two files work together

| File | Owner | Purpose |
|---|---|---|
| `PHASE_0_STABILIZE_CHECKLIST_20260416.md` | **Codex** (coding lane) | Exact commands, commit boundaries, whitelist/revertlist, gates |
| `PHASE_0_DOC_HANDOFF.md` (this file) | **Claude** (planning lane) | Documentation cadence — what gets written after each commit, where, and in what format |

Codex executes. Claude records. Neither touches the other's lane.

---

## The 5-line phase note format

After **each commit Codex lands** (not after the full phase — after each commit), Claude writes a 5-line note. This is the minimum viable audit trail. Same format every time, no deviation:

```
1. Outcome        — what the commit achieved in one sentence
2. Evidence       — how we know it worked (command output, git status, file count)
3. Files changed  — one line list (or "see commit")
4. Commit hash(es)— short SHA(s), multiple if the step produced more than one
5. Open risk / next gate — what's still exposed, or what Phase unblocks next
```

**Example (Phase 0, Commit 2 — the v3.2 engine commit):**
```
Outcome:  v3.2 engine + data-layer changes separated from CRLF noise; filter_regime column wired end-to-end in lazarus.py + db_adapter.py.
Evidence: git show --stat <SHA> shows +85/-16 across 2 files; py_compile passed on lazarus.py.
Files:    src/engine/lazarus.py, src/data/db_adapter.py
Commit:   abc1234
Risk:     config_defaults.py still untracked (Commit 3); query pack still references filter_regime (Phase 2).
```

Keep it to five lines. If a commit needs more explanation, it needed to be two commits.

---

## Where the notes live

**Primary location (during Phase 0 only):**
`docs/sprints/PHASE_0_EXECUTION_LOG.md` — a single append-only file Claude creates on first commit and adds to after each subsequent commit. One section per commit, each section is a 5-line note.

**Not yet:** do **not** write Phase 0 commit notes into the project ledger or go-live tracker. Those are canonical source-of-truth docs, and Phase 1 is where we decide whether `docs/` or `github-repo/docs/` wins. Writing into both now compounds the drift we're trying to fix.

---

## Phase 0 close-out note (what Claude writes after the whole phase lands)

Once Codex has pushed the working branch and all Phase 0 commits are in, Claude adds **one** close-out note to the project ledger. Per Codex's guidance, that note must capture four things and nothing more:

1. **Repo stabilized.** CRLF-only churn was removed from the working tree. Line-ending policy is now enforced by `.gitattributes` (landed in Commit 1).
2. **Old backlog pushed.** The local commit backlog that had built up before 2026-04-16 was pushed to origin before any new work resumed, so the v3.2 work sits on top of a clean base.
3. **v3.2 work separated.** Engine/runtime support (`lazarus.py`, `db_adapter.py`) and deploy artifacts (`config_defaults.py`, `lazarus_deploy_v32_lowvol_epoch.sh`, `WIDE_NET_V2_*`) are now in focused commits rather than mixed into line-ending noise. Each commit is independently reviewable.
4. **Canonical source-of-truth edits deferred.** No ledger-body or tracker-body edits about v3.2 performance, Stoic Gate reconciliation, or cohort numbers. Those wait for Phase 1 (pick `docs/` vs `github-repo/docs/` as canonical) and Phase 6 (server reality check reconciles memory vs tracker).

The close-out note is *about the stabilization itself*, not about v3.2 outcomes. Don't let it scope-creep.

---

## What Claude must NOT do during Phase 0

- **Do not edit the project ledger body.** Only the append-only close-out note at the end.
- **Do not update `ops/config/go_live_tracker.md`.** The 7/20 vs 25/1.73 contradiction is a Phase 6 problem, not a Phase 0 problem.
- **Do not cite Stoic Gate as "cleared"** in any doc touched during Phase 0. Memory `project_stoic_gate_unverified.md` explains why.
- **Do not touch memory files except to correct stale claims.** If a commit surfaces a fact that contradicts memory (e.g., confirms filter_regime landed on disk), update the relevant memory file with the new evidence. Otherwise leave memory alone.
- **Do not write new planning docs** until Phase 0 is fully closed out. The checklist + this handoff are the only two Phase 0 planning artifacts.

---

## What Claude *does* do between commits

- **Read each commit's diff** via `git show <SHA> --stat` once Codex reports the SHA, to confirm the file list matches the checklist's whitelist/revertlist for that step.
- **Write the 5-line note** into `PHASE_0_EXECUTION_LOG.md`.
- **Flag any deviation** from the checklist before the next commit starts. If Codex had to improvise (e.g., a revert touched a file not on the revertlist), that's a risk line in the next 5-line note, not something to bury.
- **Hold the line on gates.** If Codex asks to proceed past a gate that hasn't been met (e.g., syntax check failed but "it's probably fine"), Claude says no until the gate passes.

---

## After Phase 0 lands

1. Claude writes the single close-out note into the ledger (see section above).
2. Claude opens Phase 1: decide canonical docs location (`docs/` vs `github-repo/docs/`). This unblocks every future ledger/tracker edit.
3. Phase 2 (query pack split) and Phase 6 (server reality check) get scheduled only after Phase 1 lands, because both of those touch docs and we need to know which copy is canonical first.

---

## Why this cadence matters

The 4/3 Epoch Query Data Leak happened because nobody wrote down, at the moment of the fix, what had actually changed vs. what was assumed. The fix worked but the assumption ("strftime('%s') vs ISO text is fine") was never tested. Five-line notes force the evidence line. If you can't fill in "Evidence," the commit isn't done.

This is also the Tier 2 resume bullet: *"Instituted per-commit documentation cadence on a trading-system stabilization sprint; reduced assumption-driven defects by separating execution (Codex) from audit (Claude)."* That bullet only works if the cadence is actually followed.

---

**End of handoff. Checklist executes; this file audits.**
