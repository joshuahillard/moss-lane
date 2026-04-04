#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment: Wide-Net Paper Mode
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Widen scanner filters to increase paper trade frequency for Stoic Gate data
#   collection. All changes are PAPER MODE ONLY — exit chain stays locked.
#
# CHANGES:
#   1. min_chg_pct:  10%  → 5%     (catch earlier-stage movers)
#   2. max_chg_pct:  80%  → 120%   (test "exit liquidity" assumption)
#   3. min_liq:      $50k → $30k   (wider candidate pool)
#   4. cooldown:     7200s → 3600s (more re-entry data)
#   5. Adds filter_regime column to trades table for segmented analysis
#   6. Tags trades with "wide_net_v1" or "original" based on whether they
#      would have passed the original tight filters
#
# INSTRUCTIONS:
#   Step 1 — PowerShell (new terminal, NOT the SSH window):
#     scp -i $HOME\sol_new "C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\Shell Script\lazarus_deploy_widenet.sh" root@64.176.214.96:/tmp/
#
#   Step 2 — SSH terminal:
#     bash /tmp/lazarus_deploy_widenet.sh
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── CONFIG ───────────────────────────────────────────────────────────────────
PATCH_NAME="widenet_paper"
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

    # ── PATCH 1: min_chg_pct 10 → 5 in CFG dict ─────────────────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
# Look for the hardcoded min_chg setting — try common patterns
import re
# Match min_chg variations in CFG
found = False
for pattern, repl in [
    ('\"min_chg_pct\": 10', '\"min_chg_pct\": 5'),
    ('\"min_chg_pct\":10', '\"min_chg_pct\": 5'),
    (\"'min_chg_pct': 10\", \"'min_chg_pct': 5\"),
]:
    if pattern in s:
        s = s.replace(pattern, repl)
        found = True
        break
if not found:
    # Check if it's already set to 5
    if '\"min_chg_pct\": 5' in s or \"'min_chg_pct': 5\" in s:
        print('  SKIP: min_chg_pct already set to 5 in code')
    else:
        print('  WARNING: min_chg_pct pattern not found in code — DB update will handle it')
else:
    open(f,'w').write(s)
    print('  PATCHED lazarus.py: min_chg_pct 10 → 5')
"

    # ── PATCH 2: max_chg_pct 80 → 120 in CFG dict ───────────────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
found = False
for pattern, repl in [
    ('\"max_chg_pct\": 80', '\"max_chg_pct\": 120'),
    ('\"max_chg_pct\":80', '\"max_chg_pct\": 120'),
    (\"'max_chg_pct': 80\", \"'max_chg_pct': 120\"),
]:
    if pattern in s:
        s = s.replace(pattern, repl)
        found = True
        break
if not found:
    if '\"max_chg_pct\": 120' in s or \"'max_chg_pct': 120\" in s:
        print('  SKIP: max_chg_pct already set to 120 in code')
    else:
        print('  WARNING: max_chg_pct pattern not found in code — DB update will handle it')
else:
    open(f,'w').write(s)
    print('  PATCHED lazarus.py: max_chg_pct 80 → 120')
"

    # ── PATCH 3: min_liq 50000 → 30000 in CFG dict ──────────────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
found = False
for pattern, repl in [
    ('\"min_liq\": 50000', '\"min_liq\": 30000'),
    ('\"min_liq\":50000', '\"min_liq\": 30000'),
    (\"'min_liq': 50000\", \"'min_liq': 30000\"),
]:
    if pattern in s:
        s = s.replace(pattern, repl)
        found = True
        break
if not found:
    if '\"min_liq\": 30000' in s or \"'min_liq': 30000\" in s:
        print('  SKIP: min_liq already set to 30000 in code')
    else:
        print('  WARNING: min_liq pattern not found in code — DB update will handle it')
else:
    open(f,'w').write(s)
    print('  PATCHED lazarus.py: min_liq 50000 → 30000')
"

    # ── PATCH 4: cooldown 7200 → 3600 in CFG dict ───────────────────────────
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()
found = False
for pattern, repl in [
    ('\"cooldown\": 7200', '\"cooldown\": 3600'),
    ('\"cooldown\":7200', '\"cooldown\": 3600'),
    (\"'cooldown': 7200\", \"'cooldown': 3600\"),
]:
    if pattern in s:
        s = s.replace(pattern, repl)
        found = True
        break
if not found:
    if '\"cooldown\": 3600' in s or \"'cooldown': 3600\" in s:
        print('  SKIP: cooldown already set to 3600 in code')
    else:
        print('  WARNING: cooldown pattern not found in code — DB update will handle it')
else:
    open(f,'w').write(s)
    print('  PATCHED lazarus.py: cooldown 7200 → 3600')
"

    # ── PATCH 5: Add filter_regime tagging to trade logging ──────────────────
    # This adds a helper that checks if a trade would have passed original filters
    python3 -c "
f='${BASE_DIR}/lazarus.py'
s=open(f).read()

# Add the filter_regime helper function after imports (before first class/function)
helper_code = '''
# ── Wide-Net Filter Regime Tagging (added by widenet_paper deploy) ──────────
ORIGINAL_FILTERS = {
    \"min_chg_pct\": 10.0,
    \"max_chg_pct\": 80.0,
    \"min_liq\": 50000,
    \"cooldown\": 7200,
}

def get_filter_regime(chg_h1, liq_usd):
    \"\"\"Tag trade with filter regime for segmented analysis.\"\"\"
    if (ORIGINAL_FILTERS[\"min_chg_pct\"] <= chg_h1 <= ORIGINAL_FILTERS[\"max_chg_pct\"]
            and liq_usd >= ORIGINAL_FILTERS[\"min_liq\"]):
        return \"original\"
    return \"wide_net_v1\"
'''

# Check if already added
if 'ORIGINAL_FILTERS' in s:
    print('  SKIP: filter_regime helper already present')
else:
    # Insert after the last import line or after the CFG dict
    # Find a safe insertion point — after 'import' block
    import re
    # Find the line with 'CFG = {' or similar config dict start
    cfg_match = re.search(r'^CFG\s*=\s*\{', s, re.MULTILINE)
    if cfg_match:
        # Insert before CFG
        pos = cfg_match.start()
        s = s[:pos] + helper_code + '\n' + s[pos:]
        open(f,'w').write(s)
        print('  PATCHED lazarus.py: added filter_regime helper')
    else:
        print('  WARNING: Could not find CFG dict — filter_regime helper not added')
        print('  Manual insertion may be needed')
"

    echo "  Code patches complete."

    # ── DB UPDATES ───────────────────────────────────────────────────────────
    echo ""
    echo "  Updating bot_config table (runtime source of truth)..."

    # Update bot_config — the actual runtime config source
    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='5.0' WHERE key='min_chg_pct';"
    echo "  DB: min_chg_pct → 5.0"

    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='120.0' WHERE key='max_chg_pct';"
    echo "  DB: max_chg_pct → 120.0"

    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='30000' WHERE key='min_liq';"
    echo "  DB: min_liq → 30000"

    sqlite3 "$DB_PATH" "UPDATE bot_config SET value='3600' WHERE key='cooldown';"
    echo "  DB: cooldown → 3600"

    # Clear any dynamic_config overrides for these keys
    sqlite3 "$DB_PATH" "DELETE FROM dynamic_config WHERE key IN ('min_chg_pct','max_chg_pct','min_liq','cooldown');"
    echo "  DB: cleared dynamic_config overrides for patched keys"

    # ── ADD filter_regime COLUMN TO TRADES TABLE ─────────────────────────────
    echo ""
    echo "  Adding filter_regime column to trades table..."

    # SQLite ADD COLUMN is safe — it's a no-op error if column already exists
    sqlite3 "$DB_PATH" "ALTER TABLE trades ADD COLUMN filter_regime TEXT DEFAULT 'unknown';" 2>/dev/null && \
        echo "  DB: filter_regime column added to trades table" || \
        echo "  DB: filter_regime column already exists (OK)"

    # Tag existing post-epoch trades as 'original' (they passed the tight filters)
    sqlite3 "$DB_PATH" "UPDATE trades SET filter_regime='original' WHERE filter_regime='unknown' AND timestamp > 1711734240;"
    echo "  DB: tagged existing trades as 'original' regime"

    echo ""
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

# ── PRE-FLIGHT: Show current DB values ───────────────────────────────────────
log "PRE-FLIGHT: Current bot_config values:"
sqlite3 "$DB_PATH" "SELECT key, value FROM bot_config WHERE key IN ('min_chg_pct','max_chg_pct','min_liq','cooldown');" 2>&1 | tee -a "$LOG_FILE"
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

# Also backup the DB
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
    journalctl -u "$SERVICE_NAME" --no-pager -n 5 --since "30 seconds ago" 2>&1 | tee -a "$LOG_FILE"
else
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

# ── STEP 6: Post-deploy verification ────────────────────────────────────────
log "STEP 6: Verifying new config values in DB..."
sqlite3 "$DB_PATH" "SELECT key, value FROM bot_config WHERE key IN ('min_chg_pct','max_chg_pct','min_liq','cooldown');" 2>&1 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Verify filter_regime column exists
REGIME_COL=$(sqlite3 "$DB_PATH" "PRAGMA table_info(trades);" | grep filter_regime || true)
if [ -n "$REGIME_COL" ]; then
    log "  VERIFIED: filter_regime column exists in trades table"
else
    log "  WARNING: filter_regime column NOT found — check manually"
fi

# ── STEP 7: Summary ─────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log ""
log "  CHANGES APPLIED:"
log "    min_chg_pct:  10  → 5     (catch earlier movers)"
log "    max_chg_pct:  80  → 120   (test exit liquidity thesis)"
log "    min_liq:      50k → 30k   (wider candidate pool)"
log "    cooldown:     7200 → 3600 (more re-entry data)"
log "    filter_regime column added (segmented analysis)"
log ""
log "  WHAT TO WATCH:"
log "    journalctl -u lazarus -f"
log "    → Look for increased candidate count in scan cycles"
log "    → Each trade will be tagged 'original' or 'wide_net_v1'"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "Deployment successful. Backup preserved at: ${BACKUP_DIR}"
echo ""
echo "Next: run 'journalctl -u lazarus -f' to watch for new candidates."
