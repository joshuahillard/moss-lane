# Moss Lane Sprint Template

> Copy this template when creating a new sprint prompt for Lazarus (the Moss Lane trading engine). Fill in each section. This structure has been validated across deployments and tested with the 8-Pillar Framework for anti-hallucination and repeatability.

---

```markdown
# Moss Lane Sprint [N] — [Title]

## CONTEXT
You are working on **Moss Lane** — an autonomous Solana memecoin trading system. The trading engine is called **Lazarus**.
The project has two working locations:
1. **github-repo/** — Git repository (syncs to GitHub, where Claude Code / Codex work)
2. **Server** — Vultr VPS at 64.176.214.96 (where Lazarus runs live, deployment scripts target here)

**Read these onboarding docs before starting:**
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture, file inventory, current state
- `docs/ai-onboarding/PERSONAS.md` — Stakeholder personas and constraints
- `docs/ai-onboarding/RULES.md` — Engineering rules and incident history

**Current state**: [Describe what's deployed on server, paper/live mode, trade count, recent changes, Stoic Gate status]

**This sprint's scope**: [What this sprint adds/fixes, which working location(s) it affects]

---

## CRITICAL RULES (Anti-Hallucination)

[Copy from RULES.md, then add sprint-specific rules here]

### Sprint [N]-Specific Rules:
[List any additional constraints unique to this sprint — e.g., "Do not modify bot_config table directly", "Filter tuning locked until post-gate", etc.]

### Files That Must NOT Be Modified:
| File | Why |
|------|-----|
| lazarus.db (bot_config, dynamic_config tables) | Runtime config source of truth; changes must go through deployment scripts |
| [other protected files] | [reason] |

### Files That Require Explicit Permission (granted for this sprint):
| File | Permitted Change |
|------|-----------------|
| [file in github-repo] | [what this sprint is allowed to change] |
| [file on server] | [what this sprint is allowed to change] |

---

## PRE-FLIGHT CHECK

### For github-repo work (Claude Code / Codex):
```bash
# 1. Verify working directory
pwd
# Must be inside the github-repo/ directory

# 2. Verify branch
git branch --show-current

# 3. Recent commits
git log --oneline -5

# 4. Uncommitted changes
git status

# 5. Verify file structure (check files this sprint depends on)
ls -la [file1] [file2] [file3]

# 6. Verify files this sprint will CREATE don't exist yet
ls -la [new_file_1] 2>/dev/null && echo "ERROR: file exists" || echo "OK"
ls -la [new_file_2] 2>/dev/null && echo "ERROR: file exists" || echo "OK"
```

### For server work (Josh runs via SSH):
```bash
# 1. Verify Lazarus is running
systemctl status lazarus

# 2. Check recent trade count (post-epoch: 2026-03-29T17:44:00)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT COUNT(*) FROM trades WHERE side='sell' AND timestamp >= '2026-03-29 17:44:00';
"

# 3. Current balance snapshot
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT timestamp, balance_sol, balance_usd, pnl_total_pct
FROM balance_snapshots ORDER BY timestamp DESC LIMIT 1;
"

# 4. Last 30 log lines (check for errors)
journalctl -u lazarus --no-pager -n 30

# 5. Current bot_config (runtime settings)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT key, value FROM bot_config ORDER BY key;
"

# 6. Current dynamic_config (learning engine overrides, if any)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT key, value, epoch FROM dynamic_config ORDER BY epoch DESC;
"

# 7. Stoic Gate status (if applicable)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT COUNT(*) as gate_trades FROM trades WHERE timestamp >= '2026-03-29 17:44:00' AND side='sell';
"
```

---

## FILE INVENTORY

### Files to Create (new)
| # | File | Location | Purpose |
|---|------|----------|---------|
| 1 | [filename] | [github-repo/ or /home/solbot/lazarus/] | [What this file does] |

### Files to Modify (existing)
| # | File | Location | Changes |
|---|------|----------|---------|
| 1 | [filename] | [github-repo/ or /home/solbot/lazarus/] | [What changes are needed] |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL:
```
[list all files to be modified, with absolute paths]
```

Also read for reference (do not modify):
```
[list files needed for context, with absolute paths]
```

---

## TASK N: [Task Name]

**Read first**: [file(s) with absolute paths]

**Persona**: [HFT Quant / Data Engineer / DevOps / QA / TPM / Observability]

**Working location**: [github-repo / Server]

[Description of what to do, with context and acceptance criteria]

### For github-repo changes:
[Direct file modifications via Claude Code / Codex]

**Verification**:
```bash
[specific commands to verify this task worked — run locally in github-repo]
```

### For server deployment:
[Deployment script using `lazarus_deploy_template.sh` pattern]

**Script steps:**
1. Backup target files to `/home/solbot/backups/`
2. Apply patch (python string.replace or regex via heredoc)
3. Syntax check: `/home/solbot/lazarus/venv/bin/python3 -m py_compile [filename]`
4. Restart service: `systemctl restart lazarus`
5. Health check: `journalctl -u lazarus --no-pager -n 30`
6. Rollback on failure (restore from backup)

**Verification** (Josh runs via SSH):
```bash
[specific commands to verify this task worked on server]
```

---

## FINAL VERIFICATION

### github-repo (if files were modified):
```bash
git status
git diff --stat
# Verify no secrets in any committed files
grep -r "SOLANA_KEY\|WALLET\|SECRET" . --include="*.py" 2>/dev/null || echo "OK: no secrets"
```

### Server (Josh runs via SSH):
```bash
# Service running
systemctl status lazarus

# No errors in logs
journalctl -u lazarus --no-pager -n 30 | grep -i error || echo "OK: no errors in last 30 lines"

# Config matches expectations
sqlite3 /home/solbot/lazarus/logs/lazarus.db "SELECT key, value FROM bot_config ORDER BY key;"

# Trades flowing (verify recent trades post-epoch)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT timestamp, symbol, side, pnl_pct, exit_reason
FROM trades WHERE side='sell' AND timestamp >= '2026-03-29 17:44:00'
ORDER BY timestamp DESC LIMIT 10;
"

# Stoic Gate progress (if applicable)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT COUNT(*) as total_trades FROM trades WHERE timestamp >= '2026-03-29 17:44:00' AND side='sell';
"
```

---

## COMMIT (github-repo only, if files changed)

```bash
git add [specific files — be explicit]
git status
git commit -m "[type](scope): description

[body explaining why this change matters]

Phase: Sprint [N] — [Title]
Persona: [lead persona]
Deploy: [github-repo / server / both]"

git tag -a sprint-[N]-[version] -m "Sprint [N]: [description]"
# Do NOT push unless Josh explicitly approves
```

---

## COMPLETION CHECKLIST

- [ ] [Checklist item per deliverable]
- [ ] Server: `systemctl status lazarus` — active (running)
- [ ] Server: No errors in last 30 log lines
- [ ] Server: bot_config values match expected sprint settings
- [ ] Server: Recent trades (last 10) show correct behavior
- [ ] github-repo: Clean working tree (if files were modified)
- [ ] github-repo: No secrets in committed code
- [ ] Commit message follows template (Phase, Persona, Deploy)
- [ ] Time logged in session handoff
```
