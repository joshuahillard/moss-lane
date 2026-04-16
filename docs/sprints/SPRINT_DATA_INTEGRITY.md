# Moss Lane Sprint — Data Integrity & Layered Protection System

## CONTEXT
You are working on **Moss Lane** — an autonomous Solana memecoin trading system. The trading engine is called **Lazarus**.
The project has two working locations:
1. **github-repo/** — Git repository (syncs to GitHub, where Claude Code / Codex work)
2. **Server** — Vultr VPS at 64.176.214.96 (where Lazarus runs live, deployment scripts target here)

**Read these onboarding docs before starting:**
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture, file inventory, current state
- `docs/ai-onboarding/PERSONAS.md` — Stakeholder personas and constraints
- `docs/ai-onboarding/RULES.md` — Engineering rules and incident history

**Current state**:
- PAPER mode, $10k virtual capital, 25+ post-epoch trades (Stoic Gate CLEARED)
- V3.1 epoch: `2026-03-29T17:44:00`
- Learning engine ACTIVE — has written `stop_loss=0.94` and `position_pct=0.15` to `dynamic_config`
- Original filters outperform wide-net (50% WR / +39.52% vs 26.7% WR / +4.02%)
- Config hierarchy: Code CFG defaults → `bot_config` DB table → `dynamic_config` DB table (learning engine overrides)

**This sprint's scope**: Build a layered data integrity protection system across the learning engine, query layer, and runtime validation. This addresses the root causes behind four historical incidents (DB Config Override, Epoch Format Mismatch, Ghost Trade Bug, Epoch Query Data Leak) and prevents future classes of data leakage from poisoning trade decisions.

---

## CRITICAL RULES (Anti-Hallucination)

### Inherited from RULES.md (always active):
1. READ before WRITE — never assume file contents
2. No full file rewrites — surgical patches only
3. EnvLoader only — never python-dotenv
4. `curl_get()` for external HTTP — never aiohttp for external APIs
5. Three-Place Config Update — CFG + bot_config + DEFAULTS
6. Fail-closed scanner — rejection is default
7. JIT Final Gate — re-verify at moment of execution
8. Stoic Gate — 20-trade minimum before regime changes
9. Deployment template required — backup → patch → syntax → restart → health → rollback
10. Timestamp format — ISO T-format text comparison only, NEVER `strftime('%s',...)`

### Sprint-Specific Rules:
- **No changes to exit chain logic** — TP, SL, trail, sniper are locked during this sprint
- **No changes to scanner filters** — min_chg, max_chg, min_liq are locked
- **All new validation functions must be pure** — no side effects, no network calls, no DB writes
- **Every validation layer must log its result** — pass or fail, with the specific value that triggered the decision
- **If any layer is uncertain, it MUST fail closed** — default to rejecting the data, not accepting it

### Files That Must NOT Be Modified:
| File | Why |
|------|-----|
| lazarus.db (bot_config table) | Runtime config source of truth — not in scope for this sprint |
| .env | Credentials — never touch |

### Files That Require Explicit Permission (granted for this sprint):
| File | Permitted Change |
|------|-----------------|
| learning_engine.py (server) | Add input validation, epoch enforcement, output bounds checking |
| lazarus.py (server) | Add runtime assertion layer, config sanity checks at startup |
| github-repo/learning_engine.py | Mirror server changes |
| github-repo/lazarus.py | Mirror server changes |

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

# 5. Verify files this sprint modifies exist
ls -la learning_engine.py lazarus.py

# 6. Read current learning_engine.py epoch handling
grep -n "epoch\|strftime\|timestamp" learning_engine.py
```

### For server work (Josh runs via SSH):
```bash
# 1. Verify Lazarus is running
systemctl status lazarus

# 2. Post-epoch trade count
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT COUNT(*) as post_epoch_trades
FROM trades WHERE side='sell' AND timestamp >= '2026-03-29T17:44:00';
"

# 3. Current dynamic_config (learning engine state)
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT key, value, epoch FROM dynamic_config ORDER BY epoch DESC;
"

# 4. Current bot_config baseline
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT key, value FROM bot_config ORDER BY key;
"

# 5. Last 30 log lines (check for errors)
journalctl -u lazarus --no-pager -n 30

# 6. Verify learning_engine.py current state
head -50 /home/solbot/lazarus/learning_engine.py
grep -n "epoch\|strftime\|timestamp\|MIN_TRADES\|dynamic_config" /home/solbot/lazarus/learning_engine.py
```

---

## THE LAYERED PROTECTION MODEL

This sprint implements **five defensive layers**. Each layer operates independently — if one fails, the others still catch the problem. This is defense-in-depth, not defense-by-hope.

```
┌─────────────────────────────────────────────────────┐
│                    LAYER 5                          │
│              OBSERVABILITY ALERTS                    │
│   Log anomalies, unexpected data patterns, drift    │
├─────────────────────────────────────────────────────┤
│                    LAYER 4                          │
│           RUNTIME ASSERTION CHECKS                  │
│   Startup sanity, config bounds, epoch freshness    │
├─────────────────────────────────────────────────────┤
│                    LAYER 3                          │
│        DYNAMIC CONFIG OUTPUT VALIDATION             │
│   Bounds-check every learning engine write          │
├─────────────────────────────────────────────────────┤
│                    LAYER 2                          │
│        LEARNING ENGINE INPUT VALIDATION             │
│   Epoch gate, trade count, regime filter            │
├─────────────────────────────────────────────────────┤
│                    LAYER 1                          │
│           QUERY-LEVEL EPOCH GATING                  │
│   Correct text comparison on every DB read          │
└─────────────────────────────────────────────────────┘
```

**Design principle**: Each layer is a pure validation gate. It accepts data and returns `(valid: bool, reason: str)`. No layer modifies data. No layer has side effects beyond logging. Every layer fails closed.

---

## FILE INVENTORY

### Files to Create (new)
| # | File | Location | Purpose |
|---|------|----------|---------|
| 1 | `data_integrity.py` | github-repo/ + server | Standalone validation module — all 5 layers as importable functions |

### Files to Modify (existing)
| # | File | Location | Changes |
|---|------|----------|---------|
| 1 | `learning_engine.py` | github-repo/ + server | Import and call Layer 2 (input) + Layer 3 (output) validators |
| 2 | `lazarus.py` | github-repo/ + server | Import and call Layer 1 (query) + Layer 4 (startup assertions) + Layer 5 (anomaly logging) |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL:
```
github-repo/learning_engine.py
github-repo/lazarus.py
```

Also read for reference (do not modify):
```
github-repo/self_regulation_clean.py
docs/ai-onboarding/RULES.md
```

---

## TASK 1: Build data_integrity.py — The Validation Module

**Read first**: `github-repo/learning_engine.py`, `github-repo/lazarus.py`

**Persona**: Data Engineer (Learning Systems) + QA/Validation

**Working location**: github-repo (then mirror to server via deployment script)

Create a standalone module containing all five validation layers as pure functions. No side effects. No network calls. No DB writes. Every function returns a named tuple or dict with `(valid: bool, reason: str, details: dict)`.

### Layer 1: Query-Level Epoch Gating

```python
def validate_epoch_query(query_text: str, epoch: str = "2026-03-29T17:44:00") -> dict:
    """
    Scans a SQL query string for epoch comparison anti-patterns.

    REJECTS:
    - strftime('%s', ...) used against timestamp column
    - Unix integer comparisons against ISO text column
    - Missing epoch filter entirely (query touches trades table without timestamp filter)

    ACCEPTS:
    - Direct text comparison: timestamp >= '2026-03-29T17:44:00'
    - Parameterized equivalent

    Returns: {valid: bool, reason: str, details: {pattern_found: str}}
    """
```

**Why this exists**: The 2026-04-03 epoch query data leak. `strftime('%s',...)` returned unix integers that string-compared as always-TRUE against ISO text timestamps, leaking ALL 179 trades into a 25-trade filtered query. This turned +43.54% real PnL into an apparent -690%.

### Layer 2: Learning Engine Input Validation

```python
def validate_learning_input(trades: list, epoch: str, min_trades: int = 20) -> dict:
    """
    Validates the trade dataset BEFORE the learning engine evaluates it.

    REJECTS:
    - Trade count below MIN_TRADES (Stoic Gate)
    - Any trade with timestamp < epoch (pre-epoch data leakage)
    - Trades missing required fields (pnl_pct, exit_reason, filter_regime)
    - Trades where paper != current mode

    ACCEPTS:
    - Only post-epoch, complete trades that pass all checks

    Returns: {valid: bool, reason: str, details: {total: int, rejected: int, rejection_reasons: dict}}
    """
```

**Why this exists**: The Ghost Trade Bug. Learning engine had no MIN_TRADES gate and no epoch filter, so it kept poisoning dynamic_config from stale v2 data. Self-regulation entered a death spiral.

### Layer 3: Dynamic Config Output Validation

```python
# Bounds that the learning engine is NEVER allowed to exceed
PARAM_BOUNDS = {
    "position_pct": {"min": 0.10, "max": 0.30, "type": float},
    "stop_loss":    {"min": 0.85, "max": 0.96, "type": float},
    "take_profit":  {"min": 1.10, "max": 1.50, "type": float},
    "trail_arm":    {"min": 1.04, "max": 1.15, "type": float},
    "min_chg_pct":  {"min": 3.0,  "max": 50.0, "type": float},
    "max_chg_pct":  {"min": 50.0, "max": 200.0, "type": float},
    "min_liq":      {"min": 20000, "max": 200000, "type": float},
}

def validate_config_write(key: str, value, bounds: dict = PARAM_BOUNDS) -> dict:
    """
    Validates a proposed dynamic_config write BEFORE it hits the DB.

    REJECTS:
    - Key not in ALLOWED_KEYS (already enforced by self_regulation, this is defense-in-depth)
    - Value outside PARAM_BOUNDS min/max
    - Value type mismatch
    - NaN, None, or negative where not allowed

    ACCEPTS:
    - Key in bounds, value within range, correct type

    Returns: {valid: bool, reason: str, details: {key: str, proposed: val, min: num, max: num}}
    """
```

**Why this exists**: The learning engine once wrote 3% position sizes (from v2 data), killing trade profitability. Bounds checking prevents the learning engine from ever writing values that would cause outsized harm, even if the input data is partially compromised.

### Layer 4: Runtime Assertion Checks

```python
def validate_startup_config(bot_config: dict, dynamic_config: dict, epoch: str) -> dict:
    """
    Runs at Lazarus startup. Catches configuration drift before any trades execute.

    CHECKS:
    - bot_config has all required keys
    - dynamic_config values are within PARAM_BOUNDS
    - dynamic_config epoch is >= V3.1 epoch (no stale overrides)
    - PAPER mode flag matches expected state
    - stop_loss < take_profit (sanity)
    - position_pct * balance won't exceed per-trade risk limits

    REJECTS:
    - Any check failure prevents trading loop from starting

    Returns: {valid: bool, reason: str, details: {checks_passed: list, checks_failed: list}}
    """
```

**Why this exists**: The DB Config Override Bug. v3 deployed with updated code but the bot_config DB table still had stale v2 values. The bot ran for 8+ hours with wrong settings. A startup assertion would have caught this immediately.

### Layer 5: Observability & Anomaly Detection

```python
def check_data_anomalies(trades: list, config: dict) -> dict:
    """
    Runs periodically (e.g., every 10 trades or every hour). Detects drift.

    FLAGS:
    - Win rate dropped below 20% over last 10 trades (possible filter degradation)
    - Average PnL per trade trending negative over 3 consecutive windows
    - Learning engine hasn't updated in >50 trades (possible stall)
    - Trade volume spike (>3x normal rate — possible scanner misconfiguration)
    - All trades hitting same exit_reason (possible broken exit path)

    Does NOT reject — only logs warnings. Human (Josh) makes the call.

    Returns: {anomalies: list[dict], severity: str, recommendation: str}
    """
```

**Why this exists**: Multiple incidents were only caught when Josh manually queried the DB and noticed something looked off. This layer automates those "does this feel right?" checks and logs them proactively.

**Verification**:
```bash
# Syntax check
python3 -m py_compile data_integrity.py

# Unit test (create a minimal test)
python3 -c "
from data_integrity import validate_epoch_query, validate_learning_input, validate_config_write, validate_startup_config, check_data_anomalies

# Layer 1: should reject strftime pattern
result = validate_epoch_query(\"SELECT * FROM trades WHERE strftime('%s', timestamp) >= strftime('%s', '2026-03-29')\")
assert not result['valid'], f'Should reject strftime: {result}'

# Layer 1: should accept text comparison
result = validate_epoch_query(\"SELECT * FROM trades WHERE timestamp >= '2026-03-29T17:44:00'\")
assert result['valid'], f'Should accept text comparison: {result}'

# Layer 3: should reject out-of-bounds
result = validate_config_write('position_pct', 0.03)
assert not result['valid'], f'Should reject 3% position: {result}'

# Layer 3: should accept in-bounds
result = validate_config_write('position_pct', 0.15)
assert result['valid'], f'Should accept 15% position: {result}'

# Layer 3: should reject unknown key
result = validate_config_write('yolo_mode', True)
assert not result['valid'], f'Should reject unknown key: {result}'

print('All validation tests passed.')
"
```

---

## TASK 2: Integrate Layer 2 + Layer 3 into learning_engine.py

**Read first**: `github-repo/learning_engine.py` (FULL FILE)

**Persona**: Data Engineer (Learning Systems)

**Working location**: github-repo (then mirror to server via deployment script)

Modify `learning_engine.py` to call `validate_learning_input()` before evaluating trades, and `validate_config_write()` before every `dynamic_config` DB write.

### Integration points:

**Before trade evaluation (Layer 2)**:
```python
# WHERE: At the start of the evaluation function, before any PnL calculations
from data_integrity import validate_learning_input

input_check = validate_learning_input(trades, epoch=V31_EPOCH, min_trades=MIN_TRADES)
if not input_check["valid"]:
    logger.warning(f"[LEARNING] Input validation FAILED: {input_check['reason']} | {input_check['details']}")
    return  # Do not evaluate — fail closed
logger.info(f"[LEARNING] Input validation PASSED: {input_check['details']['total']} trades accepted")
```

**Before dynamic_config write (Layer 3)**:
```python
# WHERE: Before every INSERT/UPDATE to dynamic_config table
from data_integrity import validate_config_write

for key, value in proposed_changes.items():
    write_check = validate_config_write(key, value)
    if not write_check["valid"]:
        logger.warning(f"[LEARNING] Config write BLOCKED: {write_check['reason']} | {write_check['details']}")
        continue  # Skip this write — fail closed
    # Proceed with DB write only if validation passed
    logger.info(f"[LEARNING] Config write APPROVED: {key}={value}")
```

**Verification**:
```bash
# Syntax check
python3 -m py_compile learning_engine.py

# Grep to confirm integration
grep -n "validate_learning_input\|validate_config_write\|LEARNING.*validation\|LEARNING.*Config write" learning_engine.py
```

---

## TASK 3: Integrate Layer 1 + Layer 4 + Layer 5 into lazarus.py

**Read first**: `github-repo/lazarus.py` (focus on startup sequence and any DB query functions)

**Persona**: Senior HFT Quant (Surgical Architect) + Observability

**Working location**: github-repo (then mirror to server via deployment script)

### Layer 4 — Startup assertions (add to boot sequence):
```python
# WHERE: After config loads, before the main trading loop starts
from data_integrity import validate_startup_config

startup_check = validate_startup_config(
    bot_config=current_bot_config,
    dynamic_config=current_dynamic_config,
    epoch=V31_EPOCH
)
if not startup_check["valid"]:
    logger.critical(f"[STARTUP] ASSERTION FAILED: {startup_check['reason']}")
    logger.critical(f"[STARTUP] Failed checks: {startup_check['details']['checks_failed']}")
    logger.critical("[STARTUP] Lazarus will NOT start until this is resolved.")
    sys.exit(1)  # Hard stop — do not trade with bad config
logger.info(f"[STARTUP] All assertions passed: {startup_check['details']['checks_passed']}")
```

### Layer 5 — Periodic anomaly checks (add to monitoring loop):
```python
# WHERE: Inside the periodic monitoring function, runs every N trades or M minutes
from data_integrity import check_data_anomalies

anomaly_check = check_data_anomalies(recent_trades, current_config)
if anomaly_check["anomalies"]:
    for anomaly in anomaly_check["anomalies"]:
        logger.warning(f"[ANOMALY] {anomaly['type']}: {anomaly['message']} (severity: {anomaly['severity']})")
    if anomaly_check["severity"] == "critical":
        logger.critical(f"[ANOMALY] CRITICAL anomaly detected — recommendation: {anomaly_check['recommendation']}")
        # Log but do NOT auto-stop. Josh decides.
```

### Layer 1 — Query validation (utility for any future DB reads):
```python
# WHERE: Add as a utility function, call from any function that builds epoch-filtered SQL
from data_integrity import validate_epoch_query

def safe_epoch_query(db, query: str, params=None):
    """Wrapper that validates epoch queries before execution."""
    query_check = validate_epoch_query(query)
    if not query_check["valid"]:
        logger.error(f"[QUERY] BLOCKED unsafe epoch query: {query_check['reason']}")
        raise ValueError(f"Unsafe epoch query: {query_check['reason']}")
    return db.execute(query, params or [])
```

**Verification**:
```bash
# Syntax check
python3 -m py_compile lazarus.py

# Confirm integrations
grep -n "validate_startup_config\|check_data_anomalies\|validate_epoch_query\|safe_epoch_query\|STARTUP.*assertion\|ANOMALY" lazarus.py
```

---

## TASK 4: Server Deployment Script

**Persona**: DevOps/Release Engineer

**Working location**: Server (via deployment script)

Create a deployment script following `lazarus_deploy_template.sh` that:
1. Backs up current `lazarus.py`, `learning_engine.py` to `/home/solbot/backups/pre_data_integrity_YYYYMMDD/`
2. Copies `data_integrity.py` to `/home/solbot/lazarus/`
3. Patches `learning_engine.py` with Layer 2 + Layer 3 integration
4. Patches `lazarus.py` with Layer 1 + Layer 4 + Layer 5 integration
5. Syntax-checks ALL THREE files
6. Restarts `lazarus` service
7. Verifies health (30s log check, startup assertions should log PASSED)
8. Rollback on ANY failure

**Verification** (Josh runs via SSH):
```bash
# Service running
systemctl status lazarus

# Startup assertions passed
journalctl -u lazarus --no-pager -n 50 | grep "STARTUP"

# No errors
journalctl -u lazarus --no-pager -n 30 | grep -i error || echo "OK: no errors"

# data_integrity.py exists
ls -la /home/solbot/lazarus/data_integrity.py

# Import works
/home/solbot/lazarus/venv/bin/python3 -c "from data_integrity import validate_epoch_query; print('OK')"
```

---

## FINAL VERIFICATION

### github-repo (after all tasks):
```bash
git status
git diff --stat

# Verify no secrets
grep -r "SOLANA_KEY\|WALLET\|SECRET\|PRIVATE" . --include="*.py" 2>/dev/null || echo "OK: no secrets"

# Verify all three files pass syntax
python3 -m py_compile data_integrity.py
python3 -m py_compile learning_engine.py
python3 -m py_compile lazarus.py

# Run inline validation tests
python3 -c "
from data_integrity import validate_epoch_query, validate_config_write
assert not validate_epoch_query(\"strftime('%s', timestamp)\")['valid']
assert validate_epoch_query(\"timestamp >= '2026-03-29T17:44:00'\")['valid']
assert not validate_config_write('position_pct', 0.03)['valid']
assert validate_config_write('position_pct', 0.15)['valid']
assert not validate_config_write('yolo_mode', True)['valid']
print('All checks passed.')
"
```

### Server (Josh runs via SSH after deployment):
```bash
# Service running with new assertions
systemctl status lazarus
journalctl -u lazarus --no-pager -n 50 | grep "STARTUP\|LEARNING\|ANOMALY\|QUERY"

# No errors in last 30 lines
journalctl -u lazarus --no-pager -n 30 | grep -i error || echo "OK: no errors"

# Config still matches expectations
sqlite3 /home/solbot/lazarus/logs/lazarus.db "SELECT key, value FROM bot_config ORDER BY key;"
sqlite3 /home/solbot/lazarus/logs/lazarus.db "SELECT key, value, epoch FROM dynamic_config ORDER BY epoch DESC;"

# Trades still flowing post-deploy
sqlite3 /home/solbot/lazarus/logs/lazarus.db "
SELECT timestamp, symbol, side, pnl_pct, exit_reason
FROM trades WHERE side='sell' AND timestamp >= '2026-03-29T17:44:00'
ORDER BY timestamp DESC LIMIT 5;
"
```

---

## COMMIT (github-repo)

```bash
git add data_integrity.py learning_engine.py lazarus.py
git status
git commit -m "feat(data-integrity): add 5-layer data integrity protection system

Implements defense-in-depth validation to prevent data leakage incidents:
- Layer 1: Query-level epoch gating (blocks strftime anti-pattern)
- Layer 2: Learning engine input validation (epoch + Stoic Gate + completeness)
- Layer 3: Dynamic config output bounds checking (prevents parameter poisoning)
- Layer 4: Startup assertion checks (catches config drift before trading)
- Layer 5: Observability anomaly detection (flags drift for human review)

Each layer is a pure validation function in data_integrity.py. Layers 2-3
integrate into learning_engine.py, Layers 1/4/5 integrate into lazarus.py.
All layers fail closed. No layer modifies data.

Root cause coverage:
- DB Config Override Bug (Layer 4 catches at startup)
- Epoch Format Mismatch (Layer 2 catches in learning input)
- Ghost Trade Bug (Layer 2 Stoic Gate + epoch filter)
- Epoch Query Data Leak (Layer 1 blocks strftime pattern)

Phase: Sprint Data Integrity — Layered Protection System
Persona: Data Engineer + QA/Validation + Observability
Deploy: github-repo + server"

git tag -a sprint-di-v1.0 -m "Sprint Data Integrity: 5-layer protection system"
# Do NOT push unless Josh explicitly approves
```

---

## COMPLETION CHECKLIST

- [ ] `data_integrity.py` created with all 5 layer functions
- [ ] All inline validation tests pass
- [ ] `learning_engine.py` calls Layer 2 (input) + Layer 3 (output) validators
- [ ] `lazarus.py` calls Layer 1 (query) + Layer 4 (startup) + Layer 5 (anomaly) validators
- [ ] `python3 -m py_compile` passes on all 3 files
- [ ] Deployment script follows lazarus_deploy_template.sh pattern
- [ ] Server: `systemctl status lazarus` — active (running)
- [ ] Server: Startup assertions log `PASSED`
- [ ] Server: No errors in last 30 log lines
- [ ] Server: Trades still flowing post-deploy
- [ ] github-repo: Clean working tree, commit with proper message
- [ ] github-repo: No secrets in committed code
- [ ] Time logged in session handoff

---

## INCIDENT HISTORY (Why Each Layer Exists)

This section maps each historical incident to the layer(s) that would have prevented it.

| Incident | Date | What Broke | Root Cause | Layer(s) That Catch It |
|----------|------|-----------|------------|----------------------|
| DB Config Override | 2026-03-28 | Bot ran 8hr with stale v2 config | Code updated, DB not updated | **Layer 4** (startup assertion: required keys check) |
| Epoch Format Mismatch | 2026-03-30 | 2 pre-epoch trades leaked into learning | T-format vs space-format string comparison | **Layer 2** (input validation: timestamp < epoch) |
| Ghost Trade Bug | 2026-03-29 | Learning engine poisoned by stale data | No MIN_TRADES gate, no epoch filter | **Layer 2** (Stoic Gate + epoch filter) |
| Epoch Query Data Leak | 2026-04-03 | ALL 179 trades passed epoch filter | strftime('%s') vs ISO text = always TRUE | **Layer 1** (blocks strftime anti-pattern) |
| Learning Engine Overwrite | 2026-03-28 | 3% position size written | No bounds on dynamic_config writes | **Layer 3** (output bounds checking) |
| Silent Degradation | (prevented) | Win rate could drift without detection | No automated monitoring | **Layer 5** (anomaly detection flags drift) |
