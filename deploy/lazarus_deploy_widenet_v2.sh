#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment: Wide-Net v2 (Paper-Only Research Mode)
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Switch the VPS from Tight Execution Mode to Wide-Net v2 for paper-mode data
#   collection without reopening the weak sub-10% momentum cohort.
#
# WIDE-NET V2 PROFILE:
#   min_hourly_vol = 400   (unchanged)
#   min_chg_pct    = 10.0  (unchanged from tight mode)
#   max_chg_pct    = 100.0 (modest widen above tight 80.0)
#   min_liq        = 30000 (widen lower liquidity band for research)
#   min_vmr        = 0.10  (unchanged)
#   cooldown       = unchanged at 7200 seconds
#
# SAFETY:
#   - PAPER mode required; aborts if PAPER_TRADING is not true
#   - Backs up lazarus.db before any DB writes
#   - Clears dynamic_config overrides for filter keys to avoid drift
#   - Restarts lazarus and verifies the startup filter banner
#   - If verification fails, restores the DB backup and restarts the service
#
# INSTRUCTIONS:
#   Step 1 — PowerShell (new terminal, NOT the SSH window):
#     scp -i $HOME\sol_new "C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\deploy\lazarus_deploy_widenet_v2.sh" root@64.176.214.96:/tmp/
#
#   Step 2 — SSH terminal:
#     bash /tmp/lazarus_deploy_widenet_v2.sh
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PATCH_NAME="widenet_v2_paper"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
DB_PATH="${BASE_DIR}/logs/lazarus.db"
ENV_PATH="${BASE_DIR}/.env"
LOG_DIR="${BASE_DIR}/logs/deploys"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"
EXPECTED_FILTER_SNIPPET="Filters: chg 10.0-100.0%"
EXPECTED_LIQ_SNIPPET='liq >$30,000'

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') | $1" | tee -a "$LOG_FILE"; }

rollback() {
    log "ROLLBACK: Restoring database backup from ${BACKUP_DIR}"
    if [ -f "${BACKUP_DIR}/lazarus.db" ]; then
        cp "${BACKUP_DIR}/lazarus.db" "$DB_PATH"
        log "  RESTORED: ${DB_PATH}"
    else
        log "  WARNING: Database backup missing; nothing to restore"
    fi

    log "ROLLBACK: Restarting ${SERVICE_NAME}..."
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "ROLLBACK: Service running after DB restore."
    else
        log "ROLLBACK CRITICAL: Service failed to start after DB restore."
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

log "STEP 1: Creating backup at ${BACKUP_DIR}"
mkdir -p "$BACKUP_DIR"
cp "$DB_PATH" "${BACKUP_DIR}/lazarus.db"
log "  BACKED UP: ${DB_PATH}"

log "PRE-FLIGHT: Current bot_config values"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "STEP 2: Applying Wide-Net v2 bot_config changes"
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
log "  DB: Wide-Net v2 values written and filter-key dynamic overrides cleared"

log "STEP 3: Verifying bot_config writes"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "STEP 4: Restarting ${SERVICE_NAME}"
systemctl restart "$SERVICE_NAME"
sleep 4

log "STEP 5: Health check"
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

log "  SERVICE: active (running)"
journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"

log "STEP 6: Startup banner verification"
if journalctl -u "$SERVICE_NAME" --no-pager -n 40 --since "90 seconds ago" | grep -F "$EXPECTED_FILTER_SNIPPET" >/dev/null \
   && journalctl -u "$SERVICE_NAME" --no-pager -n 40 --since "90 seconds ago" | grep -F "$EXPECTED_LIQ_SNIPPET" >/dev/null; then
    log "  STARTUP BANNER: verified Wide-Net v2 filter banner"
else
    log "  STARTUP BANNER MISMATCH — expected '${EXPECTED_FILTER_SNIPPET}' and '${EXPECTED_LIQ_SNIPPET}'"
    rollback
    exit 1
fi

log "STEP 7: Post-deploy summary"
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
