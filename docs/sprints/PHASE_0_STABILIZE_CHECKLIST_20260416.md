# Phase 0 — Repo Stabilization Execution Checklist

**Date:** 2026-04-16
**Owner:** Josh (coding in Codex) | **Observer:** Claude (docs after each commit)
**Scope:** Repo and evidence hygiene only. No feature delivery, no server deploys, no strategy changes.
**Working branch:** `codex/stabilize-20260416`

---

## Locked choices (decided 2026-04-16)

- Repo-authoritative docs (Phase 1 will move root-level ops/sprints into the repo; Phase 0 does not touch that yet).
- Minimal migration path now; Alembic deferred to a later sprint.
- Work on a dedicated working branch, not `main`. Merge when coherent, not before.

---

## Pre-flight (one-time, before step 1)

**Windows PowerShell window.** `cd` into the repo.

```powershell
cd C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo
set GIT_PAGER=cat
```

**Clean stale git locks.** A previous session left `.git/index.lock` and `.git/objects/maintenance.lock` in place. Remove them before touching the index.

```powershell
if (Test-Path .git\index.lock)             { Remove-Item .git\index.lock }
if (Test-Path .git\objects\maintenance.lock) { Remove-Item .git\objects\maintenance.lock }
```

**Confirm starting state.**

```powershell
git rev-parse --abbrev-ref HEAD    # should print: main
git status --short | Measure-Object -Line  # expect ~30 dirty entries
git log --oneline origin/main..main        # expect: 1d96c69, 48ecba0, 72f7f8b
```

If any of the above differ, stop and reconcile before proceeding.

---

## Step 1 — Safety snapshot

**Purpose:** preserve the entire current dirty tree before any revert. If anything is reverted in error, `snapshot/pre-stabilize-20260416` is the recovery point.

```powershell
git checkout -b snapshot/pre-stabilize-20260416
git add -A
git commit -m "snapshot: pre-stabilize WIP 2026-04-16"
git checkout main
git reset --hard HEAD
```

**Verify:**
```powershell
git branch --list snapshot/pre-stabilize-20260416   # should exist
git status --short                                  # should be empty
```

**Gate:** snapshot branch exists and working tree is clean. If `git status --short` is not empty after the reset, investigate before continuing — the snapshot may have missed something.

---

## Step 2 — Push the 3 backlog commits from `main`

**Purpose:** clear the old local backlog (health endpoint, gitignore cleanup, Cloud SQL wiring) before stacking new work. This also de-risks parallel AI work later — AIs should not see a different origin/main than what's local.

```powershell
git log --oneline origin/main..main
# Expected output (in order, most recent first):
#   1d96c69 feat(health): /health endpoint + probe-based container healthcheck
#   48ecba0 chore(git): add line-ending policy and env ignore cleanup
#   72f7f8b feat(cloud-sql): wire Cloud SQL PostgreSQL + Secret Manager for Cloud Run
```

If the list matches, push:

```powershell
git push origin main
```

**Gate:** `git log --oneline origin/main..main` returns empty.

---

## Step 3 — Create the working branch

**Purpose:** all Phase 0 commits happen on `codex/stabilize-20260416`, not `main`.

```powershell
git checkout -b codex/stabilize-20260416
```

Because this branch is cut from `main` *after* the push in Step 2, no rebase is needed — the branch already sits on pushed HEAD.

**Verify:**
```powershell
git rev-parse --abbrev-ref HEAD            # codex/stabilize-20260416
git log --oneline origin/main..HEAD        # empty (no new commits yet)
```

---

## Step 4 — Identify real semantic diffs (read-only, no writes)

**Purpose:** build the whitelist of files to KEEP (real changes) and the revertlist of files that are CRLF-only.

```powershell
git status --short
git diff --stat --ignore-cr-at-eol
```

**Expected after running the above:**
- `src/engine/lazarus.py` shows `+76/-11` after --ignore-cr-at-eol
- `src/data/db_adapter.py` shows `+9/-5` after --ignore-cr-at-eol (the `filter_regime` column + write on Postgres and SQLite branches)
- `docs/MOSS_LANE_PROJECT_LEDGER.md` shows `+40/-2` after --ignore-cr-at-eol
- Every other modified file shows no output under --ignore-cr-at-eol (i.e., CRLF-only)
- Untracked: 3 deploy scripts + playbook + query pack + `src/data/config_defaults.py`

**Spot-check the three real-change files before trusting the tool:**

```powershell
git diff --ignore-cr-at-eol -- src/engine/lazarus.py | Select-String "^[+-][^+-]" | Select-Object -First 30
git diff --ignore-cr-at-eol -- src/data/db_adapter.py | Select-String "^[+-][^+-]"
git diff --ignore-cr-at-eol -- docs/MOSS_LANE_PROJECT_LEDGER.md | Select-String "^[+-][^+-]" | Select-Object -First 20
```

If any file in the revertlist below shows real content in `git diff --ignore-cr-at-eol`, STOP and reclassify it before Step 5.

**Whitelist (KEEP and commit):**
- `src/engine/lazarus.py`
- `src/data/db_adapter.py`
- `src/data/config_defaults.py` (untracked new file)
- `deploy/lazarus_deploy_v32_lowvol_epoch.sh` (untracked)
- `deploy/lazarus_deploy_widenet_v2.sh` (untracked)
- `deploy/lazarus_deploy_widenet_v2_code_db.sh` (untracked)
- `docs/reference/WIDE_NET_V2_PLAYBOOK.md` (untracked)
- `docs/reference/WIDE_NET_V2_QUERY_PACK.sql` (untracked)
- `docs/MOSS_LANE_PROJECT_LEDGER.md` (repo copy)

**Revertlist (CRLF-only, discard):**
- `deploy/deploy_phase2_fix.sh`
- `docker-compose.yml`
- `entrypoint.sh`
- `lazarus_model_meta.json`
- `src/data/migrate_sqlite_to_pg.py`
- `src/data/test_cloud_sql.py`
- `src/engine/fort_v2_clean.py`
- `src/engine/learning_engine.py`
- `src/engine/learning_engine_legacy.py`
- `src/engine/self_regulation.py`
- `src/finance/fund_splitter.py`
- `src/finance/tax_vault.py`
- `src/finance/wallet_generator.py`
- `src/ml/vertex_feature_extract.py`
- `src/ml/vertex_predict.py`
- `src/ml/vertex_train.py`
- `src/scanner/scanner_coordinator.py`
- `src/scanner/whale_watcher.py`
- `src/utils/load_test.py`
- `tests/unit/test_foundation.py`
- `tests/unit/test_fund_splitter.py`
- `docs/ai-onboarding/PERSONAS.md`
- `docs/ai-onboarding/PROJECT_CONTEXT.md`
- `docs/prompts/MOSS_LANE_MASTER_PROMPT.md`
- `docs/prompts/PORTABLE_PERSONA_LIBRARY.md`
- `docs/prompts/RUNTIME_PROMPTS.md`
- `docs/team-architecture.md`

**Gate:** whitelist and revertlist match the lists above, verified with --ignore-cr-at-eol. Do not proceed to Step 5 otherwise.

---

## Step 5 — Revert CRLF-only churn (Commit 1)

**Purpose:** restore every file in the revertlist to `HEAD` content, leaving the whitelist dirty. Explicit paths only — no blanket `git checkout --`.

```powershell
git checkout -- `
  deploy/deploy_phase2_fix.sh `
  docker-compose.yml `
  entrypoint.sh `
  lazarus_model_meta.json `
  src/data/migrate_sqlite_to_pg.py `
  src/data/test_cloud_sql.py `
  src/engine/fort_v2_clean.py `
  src/engine/learning_engine.py `
  src/engine/learning_engine_legacy.py `
  src/engine/self_regulation.py `
  src/finance/fund_splitter.py `
  src/finance/tax_vault.py `
  src/finance/wallet_generator.py `
  src/ml/vertex_feature_extract.py `
  src/ml/vertex_predict.py `
  src/ml/vertex_train.py `
  src/scanner/scanner_coordinator.py `
  src/scanner/whale_watcher.py `
  src/utils/load_test.py `
  tests/unit/test_foundation.py `
  tests/unit/test_fund_splitter.py `
  docs/ai-onboarding/PERSONAS.md `
  docs/ai-onboarding/PROJECT_CONTEXT.md `
  docs/prompts/MOSS_LANE_MASTER_PROMPT.md `
  docs/prompts/PORTABLE_PERSONA_LIBRARY.md `
  docs/prompts/RUNTIME_PROMPTS.md `
  docs/team-architecture.md
```

**Re-check after revert:**
```powershell
git status --short
# Expected remaining: exactly the whitelist (3 modified + 6 untracked)
git diff --stat --ignore-cr-at-eol
# Expected: only lazarus.py, db_adapter.py, LEDGER.md
```

Because this commit is pure cleanup and the .gitattributes normalization has already been committed (48ecba0), there is nothing to stage — the checkout discarded local modifications. **This "commit" is implicit in the revert.** Skip to Step 6 if `git status --short` shows only the whitelist.

If you prefer an explicit marker commit for changelog purposes, there's nothing to commit here (no staged changes). That's expected.

**Gate:** `git status --short` shows exactly the whitelist files and nothing else.

---

## Step 6 — Commit 2: engine/runtime changes

**Purpose:** commit the real runtime code: v3.2 low-volume epoch, startup config overrides, `filter_regime` column on both SQLite and Postgres schema paths.

**Syntax check first (mandatory per CLAUDE.md rule):**
```powershell
python -m py_compile src\engine\lazarus.py src\data\db_adapter.py src\data\config_defaults.py
# Expected: no output (success)
```

**Stage and commit:**
```powershell
git add src/engine/lazarus.py src/data/db_adapter.py src/data/config_defaults.py
git status --short
# Expected: only those three files staged
git commit -m "feat(engine): add v3.2 runtime config and filter_regime column

- lazarus.py: v3.2_lowvol_epoch filter regime (vol=250, chg=10-120, liq=30k)
- lazarus.py: _apply_startup_config_overrides with STARTUP_OVERRIDE_KEYS whitelist
- lazarus.py: filter_regime TEXT DEFAULT 'unknown' on trades table (create + insert)
- db_adapter.py: mirror filter_regime column on SQLite and Postgres schema paths
- db_adapter.py: filter_regime written on log_trade (kwargs.get fallback 'unknown')
- config_defaults.py: new module documenting canonical repo-side defaults

Runtime truth remains: code CFG -> bot_config -> dynamic_config.
Schema change on CREATE TABLE IF NOT EXISTS is a no-op for existing DBs;
Phase 3 will add the migration path that safely applies this column to
pre-v3.2 server DBs."
```

**Capture the commit hash for the Phase 0 close-out note.**

**Gate:** `git log --oneline -1` prints a single `feat(engine):` commit. `git status --short` now shows only the untracked deploy/docs files.

---

## Step 7 — Commit 3: deploy artifacts + research docs

**Purpose:** commit the v3.2 deploy script, wide-net v2 deploy scripts, playbook, query pack, and the repo ledger update describing this state.

```powershell
git add `
  deploy/lazarus_deploy_v32_lowvol_epoch.sh `
  deploy/lazarus_deploy_widenet_v2.sh `
  deploy/lazarus_deploy_widenet_v2_code_db.sh `
  docs/reference/WIDE_NET_V2_PLAYBOOK.md `
  docs/reference/WIDE_NET_V2_QUERY_PACK.sql `
  docs/MOSS_LANE_PROJECT_LEDGER.md

git status --short
# Expected: only those 6 files staged. Working tree clean otherwise.

git commit -m "feat(ops): add v3.2 deploy artifacts and research documentation

- deploy/lazarus_deploy_v32_lowvol_epoch.sh: VPS deploy with ALTER TABLE prelude
- deploy/lazarus_deploy_widenet_v2.sh: DB-only validator for wide-net v2 profile
- deploy/lazarus_deploy_widenet_v2_code_db.sh: code+DB deploy for wide-net v2
- docs/reference/WIDE_NET_V2_PLAYBOOK.md: research profile + v3.2 rationale
- docs/reference/WIDE_NET_V2_QUERY_PACK.sql: cohort analysis queries
- docs/MOSS_LANE_PROJECT_LEDGER.md: 2026-04-15 v3.2 entry + TD-006 filter drift note

Query pack currently assumes filter_regime exists. Phase 2 will split this
into legacy + post-v3.2 packs so evidence runs against any schema state.
Deploy scripts still do live schema mutation; Phase 3 migration work will
promote that out of the ad-hoc VPS patch flow."
```

**Gate:** `git log --oneline -2` shows exactly the two new commits. `git status --short` is empty.

---

## Step 8 — Push the working branch

**Purpose:** make the branch visible to origin so other AIs can read it without pulling from the laptop. Do NOT merge into main yet — Phase 1 documentation decisions need to land first.

```powershell
git push -u origin codex/stabilize-20260416
```

**Verify:**
```powershell
git log --oneline origin/codex/stabilize-20260416..HEAD   # empty (pushed)
git log --oneline origin/main..origin/codex/stabilize-20260416
# Expected: the two new feat(...) commits
```

**Gate:** branch visible on `origin`, two commits ahead of `origin/main`.

---

## Commit boundaries (summary)

| # | Title | Scope | Verification |
|---|---|---|---|
| 1 | (implicit revert — no commit) | Discard CRLF-only churn across src/, tests/, docs/, deploy/ | `git status --short` shows only whitelist after revert |
| 2 | `feat(engine): add v3.2 runtime config and filter_regime column` | Runtime code + defaults module | `python -m py_compile` on all three files; manual spot-check of diff |
| 3 | `feat(ops): add v3.2 deploy artifacts and research documentation` | Deploy scripts + playbook + query pack + repo ledger | `ls` confirms all 6 files tracked; no untracked residue |

---

## What Phase 0 explicitly does NOT do

- Does not deploy anything to the VPS or Cloud Run.
- Does not change filter behavior at runtime.
- Does not decide repo-vs-root documentation canonicalization (Phase 1).
- Does not modify the query pack for backward compatibility (Phase 2).
- Does not promote migrations out of the deploy script (Phase 3).
- Does not update `ops/config/go_live_tracker.md` decision language (Phase 4a).
- Does not touch `test_foundation.py` (Phase 5).
- Does not merge `codex/stabilize-20260416` into `main`.

---

## Open risk register at Phase 0 close

| Risk | Mitigated by |
|---|---|
| Codex's whitelist misses a real-change file buried under CRLF | Snapshot branch `snapshot/pre-stabilize-20260416` is recoverable |
| `git checkout --` destructive if file classification is wrong | Explicit path list; `--ignore-cr-at-eol` verification gate before revert |
| CRLF might reintroduce on next Windows save | `.gitattributes` + `48ecba0` already handle normalization on commit |
| Working branch drifts from main while other phases run | Push immediately (Step 8); rebase or merge into main only when Phase 1-3 cohere |

---

## Next gate (trigger for Phase 1)

Phase 1 (canonicalization decision) starts after:
- `codex/stabilize-20260416` is pushed with both feat commits.
- Claude has written the Phase 0 close-out note (see `PHASE_0_DOC_HANDOFF.md`).
- Josh confirms the decision to move root-level `ops/`, `docs/sprints/`, and `docs/DEPLOY_PIPELINE.md` into the repo.
