#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment: Wide-Net v2 (Code + DB)
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Activate Wide-Net v2 on the VPS when scanner thresholds are still sourced
#   from the hardcoded CFG dict at startup instead of bot_config.
#
# PROFILE:
#   min_hourly_vol = 400   (unchanged)
#   min_chg_pct    = 10.0  (unchanged)
#   max_chg_pct    = 100.0 (was 80.0)
#   min_liq        = 30000 (was 50000)
#   min_vmr        = 0.10  (unchanged)
#   cooldown       = 7200  (unchanged)
#
# SAFETY:
#   - PAPER mode required
#   - Backs up lazarus.py and lazarus.db
#   - Updates code and bot_config together
#   - Clears filter-key dynamic_config overrides
#   - py_compile before restart
#   - Rollback restores both file and DB on any failure
#
# INSTRUCTIONS:
#   Step 1 — PowerShell (new terminal, NOT the SSH window):
#     scp -i $HOME\sol_new "C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\deploy\lazarus_deploy_widenet_v2_code_db.sh" root@64.176.214.96:/tmp/
#
#   Step 2 — SSH terminal:
#     bash /tmp/lazarus_deploy_widenet_v2_code_db.sh
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PATCH_NAME="widenet_v2_code_db"
VENV_PYTHON="/home/solbot/lazarus/venv/bin/python3"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
DB_PATH="${BASE_DIR}/logs/lazarus.db"
ENV_PATH="${BASE_DIR}/.env"
TARGET_FILE="${BASE_DIR}/lazarus.py"
LOG_DIR="${BASE_DIR}/logs/deploys"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"
EXPECTED_FILTER_SNIPPET="Filters: chg 10.0-100.0%"
EXPECTED_LIQ_SNIPPET='liq >$30,000'

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') | $1" | tee -a "$LOG_FILE"; }

rollback() {
    log "ROLLBACK: Restoring backups from ${BACKUP_DIR}"

    if [ -f "${BACKUP_DIR}/lazarus.py" ]; then
        cp "${BACKUP_DIR}/lazarus.py" "$TARGET_FILE"
        log "  RESTORED: ${TARGET_FILE}"
    fi

    if [ -f "${BACKUP_DIR}/lazarus.db" ]; then
        cp "${BACKUP_DIR}/lazarus.db" "$DB_PATH"
        log "  RESTORED: ${DB_PATH}"
    fi

    log "ROLLBACK: Restarting ${SERVICE_NAME}..."
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "ROLLBACK: Service running after restore."
    else
        log "ROLLBACK CRITICAL: Service failed to start after restore."
    fi
}

require_paper_mode() {
    if [ ! -f "$ENV_PATH" ]; then
        log "ABORT: ${ENV_PATH} not found"
        exit 1
    fi

    local paper_value
    paper_value=$(grep -E '^PAPER_TRADING=' "$ENV_PATH" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | tr '[:upper:]' '[:lower:]' || true)

    if [ "$paper_value" != "true" ]; then
        log "ABORT: PAPER_TRADING is not true in ${ENV_PATH}. Wide-Net v2 is paper-only."
        exit 1
    fi

    log "PRE-FLIGHT: PAPER_TRADING=true confirmed."
}

mkdir -p "$LOG_DIR"

log "════════════════════════════════════════════════════════════════"
log "DEPLOY START: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

require_paper_mode

log "STEP 1: Creating backups at ${BACKUP_DIR}"
mkdir -p "$BACKUP_DIR"
cp "$TARGET_FILE" "${BACKUP_DIR}/lazarus.py"
cp "$DB_PATH" "${BACKUP_DIR}/lazarus.db"
log "  BACKED UP: ${TARGET_FILE}"
log "  BACKED UP: ${DB_PATH}"

log "PRE-FLIGHT: Current hardcoded CFG values"
grep -n "min_chg_pct\|max_chg_pct\|min_liq\|min_vmr\|min_hourly_vol" "$TARGET_FILE" | head -5 | tee -a "$LOG_FILE"

log "PRE-FLIGHT: Current bot_config values"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "STEP 2: Patching hardcoded CFG for Wide-Net v2"
python3 -c "
from pathlib import Path
f = Path('${TARGET_FILE}')
s = f.read_text()

pairs = [
    (
        '\"max_chg_pct\":      80.0,       # raised from 60 — data shows 30-80% is the sweet spot',
        '\"max_chg_pct\":      100.0,      # widened for wide_net_v2 paper research (was 80.0)'
    ),
    (
        '\"min_liq\":          50_000,     # minimum liquidity (sub-50K is graveyard)',
        '\"min_liq\":          30_000,     # widened for wide_net_v2 paper research (was 50_000)'
    ),
]

for old, new in pairs:
    if old in s:
        s = s.replace(old, new)
    elif new in s:
        pass
    else:
        raise SystemExit(f'PATCH FAILED: expected pattern not found: {old}')

f.write_text(s)
print('  PATCHED lazarus.py for Wide-Net v2')
"

log "STEP 3: Updating bot_config to match Wide-Net v2"
sqlite3 "$DB_PATH" "
BEGIN IMMEDIATE;
UPDATE bot_config SET value='400'   WHERE key='min_hourly_vol';
UPDATE bot_config SET value='10.0'  WHERE key='min_chg_pct';
UPDATE bot_config SET value='100.0' WHERE key='max_chg_pct';
UPDATE bot_config SET value='30000' WHERE key='min_liq';
UPDATE bot_config SET value='0.10'  WHERE key='min_vmr';
DELETE FROM dynamic_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr');
COMMIT;
"
log "  DB: bot_config updated and filter-key dynamic overrides cleared"

log "STEP 4: Python syntax verification"
if ! $VENV_PYTHON -m py_compile "$TARGET_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    log "  SYNTAX FAIL — initiating rollback"
    rollback
    exit 1
fi
log "  SYNTAX OK: ${TARGET_FILE}"

log "STEP 5: Restarting ${SERVICE_NAME}"
systemctl restart "$SERVICE_NAME"
sleep 4

log "STEP 6: Health check"
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi
log "  SERVICE: active (running)"
journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"

log "STEP 7: Startup banner verification"
if journalctl -u "$SERVICE_NAME" --no-pager -n 40 --since "90 seconds ago" | grep -F "$EXPECTED_FILTER_SNIPPET" >/dev/null \
   && journalctl -u "$SERVICE_NAME" --no-pager -n 40 --since "90 seconds ago" | grep -F "$EXPECTED_LIQ_SNIPPET" >/dev/null; then
    log "  STARTUP BANNER: verified Wide-Net v2 filter banner"
else
    log "  STARTUP BANNER MISMATCH — expected '${EXPECTED_FILTER_SNIPPET}' and '${EXPECTED_LIQ_SNIPPET}'"
    rollback
    exit 1
fi

log "STEP 8: Post-deploy verification"
grep -n "min_chg_pct\|max_chg_pct\|min_liq\|min_vmr\|min_hourly_vol" "$TARGET_FILE" | head -5 | tee -a "$LOG_FILE"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "Wide-Net v2 is active in PAPER mode."
echo "Next check:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} --no-pager -n 30"
