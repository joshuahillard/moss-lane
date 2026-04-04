#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment: Wide-Net Fix — Hardcoded CFG + filter_regime wiring
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   The first widenet deploy updated the DB but the bot reads from the hardcoded
#   CFG dict (DB is only used by self-regulation, which is disabled in paper).
#   This patch fixes the actual hardcoded values and wires filter_regime tagging
#   into the record_trade function.
#
# CHANGES:
#   1. CFG["min_chg_pct"]      10.0  → 5.0
#   2. CFG["max_chg_pct"]      80.0  → 120.0
#   3. CFG["min_liq"]          50000 → 30000
#   4. CFG["cooldown_seconds"] 7200  → 3600
#   5. filter_regime tagging wired into record_trade INSERT
#   6. Cleanup: remove orphan 'cooldown' key from bot_config DB
#
# INSTRUCTIONS:
#   Step 1 — PowerShell (new terminal, NOT the SSH window):
#     scp -i $HOME\sol_new "C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\Shell Script\lazarus_deploy_widenet_fix.sh" root@64.176.214.96:/tmp/
#
#   Step 2 — SSH terminal:
#     bash /tmp/lazarus_deploy_widenet_fix.sh
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── CONFIG ───────────────────────────────────────────────────────────────────
PATCH_NAME="widenet_fix"
VENV_PYTHON="/home/solbot/lazarus/venv/bin/python3"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
LOG_DIR="${BASE_DIR}/logs/deploys"
DB_PATH="${BASE_DIR}/logs/lazarus.db"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"

# ── TARGET FILES ─────────────────────────────────────────────────────────────
TARGET_FILES=(
    "${BASE_DIR}/lazarus.py"
)

# ══════════════════════════════════════════════════════════════════════════════
# PATCH DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
apply_patches() {

    # ── PATCH 1: min_chg_pct 10.0 → 5.0 in hardcoded CFG ────────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
old='\"min_chg_pct\":      10.0,       # lowered from 20 — opens the entry window'
new='\"min_chg_pct\":      5.0,        # widened for paper data collection (was 10.0)'
assert old in s, f'PATCH 1 FAILED: min_chg_pct pattern not found'
s = s.replace(old, new)
open(f,'w').write(s)
print('  PATCHED: min_chg_pct 10.0 → 5.0')
"

    # ── PATCH 2: max_chg_pct 80.0 → 120.0 in hardcoded CFG ──────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
old='\"max_chg_pct\":      80.0,       # raised from 60 — data shows 30-80% is the sweet spot'
new='\"max_chg_pct\":      120.0,      # widened for paper data collection (was 80.0)'
assert old in s, f'PATCH 2 FAILED: max_chg_pct pattern not found'
s = s.replace(old, new)
open(f,'w').write(s)
print('  PATCHED: max_chg_pct 80.0 → 120.0')
"

    # ── PATCH 3: min_liq 50_000 → 30_000 in hardcoded CFG ───────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
old='\"min_liq\":          50_000,     # minimum liquidity (sub-50K is graveyard)'
new='\"min_liq\":          30_000,     # widened for paper data collection (was 50_000)'
assert old in s, f'PATCH 3 FAILED: min_liq pattern not found'
s = s.replace(old, new)
open(f,'w').write(s)
print('  PATCHED: min_liq 50_000 → 30_000')
"

    # ── PATCH 4: cooldown_seconds 7200 → 3600 in hardcoded CFG ──────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
old='\"cooldown_seconds\":     7200,   # 2 HOURS per-token cooldown after exit'
new='\"cooldown_seconds\":     3600,   # 1 HOUR per-token cooldown for paper data collection (was 7200)'
assert old in s, f'PATCH 4 FAILED: cooldown_seconds pattern not found'
s = s.replace(old, new)
open(f,'w').write(s)
print('  PATCHED: cooldown_seconds 7200 → 3600')
"

    # ── PATCH 5: Wire filter_regime into record_trade INSERT ─────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()

# --- 5a: Add filter_regime to the INSERT column list ---
old_cols = 'entry, tx_buy, tx_sell, peak_pnl_pct)'
new_cols = 'entry, tx_buy, tx_sell, peak_pnl_pct, filter_regime)'
assert old_cols in s, f'PATCH 5a FAILED: INSERT column list pattern not found'
s = s.replace(old_cols, new_cols, 1)
print('  PATCHED: added filter_regime to INSERT column list')

# --- 5b: Add one more ? placeholder to VALUES ---
old_vals = 'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
new_vals = 'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
assert old_vals in s, f'PATCH 5b FAILED: VALUES placeholder pattern not found'
s = s.replace(old_vals, new_vals, 1)
print('  PATCHED: added ? placeholder for filter_regime')

# --- 5c: Add filter_regime value to the tuple ---
# The tuple ends with: kwargs.get(\"peak_pnl_pct\")))
old_tuple = 'tx_buy, tx_sell, kwargs.get(\"peak_pnl_pct\")))'
# Compute filter_regime inline based on chg_pct and liq kwargs
new_tuple = '''tx_buy, tx_sell, kwargs.get(\"peak_pnl_pct\"),
                 \"original\" if (10.0 <= kwargs.get(\"chg_pct\", 0) <= 80.0
                     and kwargs.get(\"liq\", 0) >= 50000) else \"wide_net_v1\"))'''
assert old_tuple in s, f'PATCH 5c FAILED: tuple end pattern not found'
s = s.replace(old_tuple, new_tuple, 1)
print('  PATCHED: added filter_regime computation to INSERT tuple')

open(f,'w').write(s)
print('  filter_regime wiring complete')
"

    echo "  Code patches complete."

    # ── DB CLEANUP ───────────────────────────────────────────────────────────
    echo ""
    echo "  Cleaning up DB..."

    # Remove orphan 'cooldown' key (wrong name, created by first deploy)
    sqlite3 "$DB_PATH" "DELETE FROM bot_config WHERE key='cooldown';"
    echo "  DB: removed orphan 'cooldown' key"

    # Sync bot_config with new CFG values (for when self-regulation re-enables)
    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='5.0' WHERE key='min_chg_pct';"
    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='120.0' WHERE key='max_chg_pct';"
    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='30000' WHERE key='min_liq';"
    echo "  DB: bot_config synced with new CFG values"

    echo "  All DB updates complete."
}

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT ENGINE — do not edit below this line
# ══════════════════════════════════════════════════════════════════════════════

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') | $1" | tee -a "$LOG_FILE"; }

rollback() {
    log "ROLLBACK: Restoring all files from ${BACKUP_DIR}"
    for f in "${TARGET_FILES[@]}"; do
        fname=$(basename "$f")
        if [ -f "${BACKUP_DIR}/${fname}" ]; then
            cp "${BACKUP_DIR}/${fname}" "$f"
            log "  RESTORED: $f"
        fi
    done
    log "ROLLBACK: Restarting service with original files..."
    systemctl restart "$SERVICE_NAME"
    sleep 3
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "ROLLBACK: Service running with original files. Patch ABORTED safely."
    else
        log "ROLLBACK CRITICAL: Service failed to start even with original files!"
        log "  Manual intervention required. Backup at: ${BACKUP_DIR}"
    fi
}

# ── STEP 0: Create log directory ─────────────────────────────────────────────
mkdir -p "$LOG_DIR"

log "════════════════════════════════════════════════════════════════"
log "DEPLOY START: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

# ── PRE-FLIGHT: Show current CFG values via grep ─────────────────────────────
log "PRE-FLIGHT: Current hardcoded CFG values:"
grep -n "min_chg_pct\|max_chg_pct\|min_liq\|cooldown_seconds" "${BASE_DIR}/lazarus.py" | head -4 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# ── STEP 1: Backup all target files ─────────────────────────────────────────
log "STEP 1: Creating backup at ${BACKUP_DIR}"
mkdir -p "$BACKUP_DIR"

for f in "${TARGET_FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "${BACKUP_DIR}/$(basename "$f")"
        log "  BACKED UP: $f"
    else
        log "  WARNING: $f does not exist — skipping backup"
    fi
done

cp "$DB_PATH" "${BACKUP_DIR}/lazarus.db"
log "  BACKED UP: $DB_PATH"

# ── STEP 2: Apply patches ───────────────────────────────────────────────────
log "STEP 2: Applying patches..."
if ! apply_patches 2>&1 | tee -a "$LOG_FILE"; then
    log "PATCH APPLICATION FAILED"
    rollback
    exit 1
fi

# ── STEP 3: Syntax verification ─────────────────────────────────────────────
log "STEP 3: Verifying Python syntax..."
SYNTAX_OK=true
for f in "${TARGET_FILES[@]}"; do
    if [ -f "$f" ]; then
        if $VENV_PYTHON -m py_compile "$f" 2>&1 | tee -a "$LOG_FILE"; then
            log "  SYNTAX OK: $f"
        else
            log "  SYNTAX FAIL: $f"
            SYNTAX_OK=false
        fi
    fi
done

if [ "$SYNTAX_OK" = false ]; then
    log "SYNTAX VERIFICATION FAILED — initiating rollback"
    rollback
    exit 1
fi

# ── STEP 4: Restart service ─────────────────────────────────────────────────
log "STEP 4: Restarting ${SERVICE_NAME}..."
systemctl restart "$SERVICE_NAME"
sleep 3

# ── STEP 5: Health check ────────────────────────────────────────────────────
log "STEP 5: Health check..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE: active (running)"
    journalctl -u "$SERVICE_NAME" --no-pager -n 8 --since "30 seconds ago" 2>&1 | tee -a "$LOG_FILE"
else
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

# ── STEP 6: Post-deploy verification ────────────────────────────────────────
log "STEP 6: Verifying new values..."
echo "  Hardcoded CFG (should show new values):" | tee -a "$LOG_FILE"
grep -n "min_chg_pct\|max_chg_pct\|min_liq\|cooldown_seconds" "${BASE_DIR}/lazarus.py" | head -4 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "  bot_config DB (should match):" | tee -a "$LOG_FILE"
sqlite3 "$DB_PATH" "SELECT key, value FROM bot_config WHERE key IN ('min_chg_pct','max_chg_pct','min_liq','cooldown_minutes') ORDER BY key;" 2>&1 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Verify filter_regime is in the INSERT
if grep -q "filter_regime" "${BASE_DIR}/lazarus.py"; then
    log "  VERIFIED: filter_regime wired into lazarus.py"
else
    log "  WARNING: filter_regime NOT found in lazarus.py"
fi

# ── STEP 7: Summary ─────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log ""
log "  WHAT CHANGED:"
log "    CFG min_chg_pct:      10.0  → 5.0"
log "    CFG max_chg_pct:      80.0  → 120.0"
log "    CFG min_liq:          50000 → 30000"
log "    CFG cooldown_seconds: 7200  → 3600"
log "    record_trade: filter_regime tagging wired in"
log ""
log "  VERIFY WITH:"
log "    journalctl -u lazarus -f"
log "    → Startup banner should show: chg 5.0-120.0% | liq >\$30,000"
log "    → Filter breakdown: chg_low and chg_high rejections should drop"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "Deployment successful. Backup preserved at: ${BACKUP_DIR}"
echo ""
echo "Next: run 'journalctl -u lazarus -f' to verify new filter values in action."
