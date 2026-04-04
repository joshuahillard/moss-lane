#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment — Data Integrity 5-Layer Protection System
# ══════════════════════════════════════════════════════════════════════════════
#
# USAGE:
#   1. SCP files from PowerShell:
#        scp -i $HOME\sol_new lazarus_deploy_data_integrity.sh root@64.176.214.96:/tmp/
#        scp -i $HOME\sol_new github-repo/data_integrity.py root@64.176.214.96:/tmp/
#        scp -i $HOME\sol_new github-repo/learning_engine.py root@64.176.214.96:/tmp/
#        scp -i $HOME\sol_new github-repo/lazarus.py root@64.176.214.96:/tmp/
#   2. SSH in and run:
#        bash /tmp/lazarus_deploy_data_integrity.sh
#
# WHAT THIS DEPLOYS:
#   - NEW: data_integrity.py (standalone 5-layer validation module)
#   - UPDATED: learning_engine.py (Layer 2 input + Layer 3 output validation)
#   - UPDATED: lazarus.py (Layer 1 query + Layer 4 startup + Layer 5 anomaly)
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── CONFIG ───────────────────────────────────────────────────────────────────
PATCH_NAME="data_integrity_5layer"
VENV_PYTHON="/home/solbot/lazarus/venv/bin/python3"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
LOG_DIR="${BASE_DIR}/logs/deploys"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"
STAGING="/tmp"

# ── TARGET FILES ─────────────────────────────────────────────────────────────
TARGET_FILES=(
    "${BASE_DIR}/lazarus.py"
    "${BASE_DIR}/learning_engine.py"
)

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT ENGINE
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
    # Remove data_integrity.py if it was newly added
    if [ -f "${BACKUP_DIR}/.data_integrity_was_new" ]; then
        rm -f "${BASE_DIR}/data_integrity.py"
        log "  REMOVED: data_integrity.py (was newly added)"
    elif [ -f "${BACKUP_DIR}/data_integrity.py" ]; then
        cp "${BACKUP_DIR}/data_integrity.py" "${BASE_DIR}/data_integrity.py"
        log "  RESTORED: data_integrity.py"
    fi
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

# ── STEP 0: Create log directory + verify staging files exist ────────────────
mkdir -p "$LOG_DIR"

log "════════════════════════════════════════════════════════════════"
log "DEPLOY START: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

# Verify all staged files are present
for fname in data_integrity.py learning_engine.py lazarus.py; do
    if [ ! -f "${STAGING}/${fname}" ]; then
        log "FATAL: ${STAGING}/${fname} not found. SCP all files first."
        exit 1
    fi
    log "  STAGED: ${STAGING}/${fname}"
done

# ── STEP 1: Backup all target files ──────────────────────────────────────────
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

# Backup data_integrity.py if it already exists, otherwise mark as new
if [ -f "${BASE_DIR}/data_integrity.py" ]; then
    cp "${BASE_DIR}/data_integrity.py" "${BACKUP_DIR}/data_integrity.py"
    log "  BACKED UP: ${BASE_DIR}/data_integrity.py"
else
    touch "${BACKUP_DIR}/.data_integrity_was_new"
    log "  data_integrity.py is NEW (no backup needed)"
fi

# ── STEP 2: Copy staged files to server ──────────────────────────────────────
log "STEP 2: Copying staged files..."
cp "${STAGING}/data_integrity.py" "${BASE_DIR}/data_integrity.py"
log "  COPIED: data_integrity.py"
cp "${STAGING}/learning_engine.py" "${BASE_DIR}/learning_engine.py"
log "  COPIED: learning_engine.py"
cp "${STAGING}/lazarus.py" "${BASE_DIR}/lazarus.py"
log "  COPIED: lazarus.py"

# ── STEP 3: Syntax verification ──────────────────────────────────────────────
log "STEP 3: Verifying Python syntax..."
SYNTAX_OK=true
for fname in data_integrity.py learning_engine.py lazarus.py; do
    f="${BASE_DIR}/${fname}"
    if $VENV_PYTHON -m py_compile "$f" 2>&1 | tee -a "$LOG_FILE"; then
        log "  SYNTAX OK: $f"
    else
        log "  SYNTAX FAIL: $f"
        SYNTAX_OK=false
    fi
done

if [ "$SYNTAX_OK" = false ]; then
    log "SYNTAX VERIFICATION FAILED — initiating rollback"
    rollback
    exit 1
fi

# ── STEP 4: Quick import test ────────────────────────────────────────────────
log "STEP 4: Import verification..."
cd "$BASE_DIR"
if $VENV_PYTHON -c "from data_integrity import validate_epoch_query, validate_startup_config, check_data_anomalies; print('  data_integrity imports OK')" 2>&1 | tee -a "$LOG_FILE"; then
    log "  IMPORT OK: data_integrity"
else
    log "  IMPORT FAIL: data_integrity — initiating rollback"
    rollback
    exit 1
fi

# ── STEP 5: Restart service ──────────────────────────────────────────────────
log "STEP 5: Restarting ${SERVICE_NAME}..."
systemctl restart "$SERVICE_NAME"
sleep 5

# ── STEP 6: Health check ─────────────────────────────────────────────────────
log "STEP 6: Health check (30s)..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE: active (running)"
else
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 30 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

# Check startup assertions in logs
sleep 25
STARTUP_LINES=$(journalctl -u "$SERVICE_NAME" --no-pager -n 50 --since "60 seconds ago" 2>&1)
echo "$STARTUP_LINES" | tee -a "$LOG_FILE"

if echo "$STARTUP_LINES" | grep -q "STARTUP.*ASSERTION FAILED"; then
    log "  STARTUP ASSERTION FAILED — initiating rollback"
    rollback
    exit 1
fi

if echo "$STARTUP_LINES" | grep -q "STARTUP.*assertions passed"; then
    log "  STARTUP ASSERTIONS: PASSED"
fi

# Check for Python errors
ERROR_COUNT=$(echo "$STARTUP_LINES" | grep -ci "error\|traceback\|exception" || true)
if [ "$ERROR_COUNT" -gt 0 ]; then
    log "  WARNING: ${ERROR_COUNT} error-like lines found in startup logs (review above)"
fi

# ── STEP 7: Summary ──────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log "  Files deployed:"
log "    NEW:     ${BASE_DIR}/data_integrity.py"
log "    UPDATED: ${BASE_DIR}/learning_engine.py"
log "    UPDATED: ${BASE_DIR}/lazarus.py"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "Deployment successful. Backup preserved at: ${BACKUP_DIR}"
echo ""
echo "POST-DEPLOY VERIFICATION:"
echo "  systemctl status lazarus"
echo "  journalctl -u lazarus --no-pager -n 50 | grep 'STARTUP\|LEARNING\|ANOMALY\|QUERY'"
echo "  sqlite3 ${BASE_DIR}/logs/lazarus.db \"SELECT key, value FROM dynamic_config ORDER BY key;\""
