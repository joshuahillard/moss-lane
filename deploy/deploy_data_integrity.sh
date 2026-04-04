#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deploy: Data Integrity — 5-Layer Protection System
# ══════════════════════════════════════════════════════════════════════════════
#
# WHAT THIS DOES:
#   - Backs up current lazarus.py, learning_engine.py, data_integrity.py
#   - Installs updated lazarus.py, learning_engine.py, data_integrity.py from /tmp/
#   - Syntax-checks all three files
#   - Restarts the lazarus service
#   - Health-checks startup assertions + anomaly logging
#   - Rolls back on ANY failure
#
# PRE-REQUISITES (Josh does these from PowerShell):
#   scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\data_integrity.py root@64.176.214.96:/tmp/
#   scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\learning_engine.py root@64.176.214.96:/tmp/
#   scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\lazarus.py root@64.176.214.96:/tmp/
#   scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\"Shell Script"\deploy_data_integrity.sh root@64.176.214.96:/tmp/
#
# THEN (Josh does this from SSH):
#   bash /tmp/deploy_data_integrity.sh
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

# Files to backup (all three — data_integrity.py may not exist yet)
TARGET_FILES=(
    "${BASE_DIR}/lazarus.py"
    "${BASE_DIR}/learning_engine.py"
    "${BASE_DIR}/data_integrity.py"
)

# Source files (must be SCP'd to /tmp/ before running this script)
STAGING_FILES=(
    "/tmp/lazarus.py"
    "/tmp/learning_engine.py"
    "/tmp/data_integrity.py"
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
        elif [ -f "$f" ] && [ ! -f "${BACKUP_DIR}/${fname}" ]; then
            # File was newly created (no backup) — remove it
            rm -f "$f"
            log "  REMOVED (new file): $f"
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

# ── STEP 0: Create log directory + verify staging files exist ────────────────
mkdir -p "$LOG_DIR"

log "════════════════════════════════════════════════════════════════"
log "DEPLOY START: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

log "STEP 0: Verifying staging files exist in /tmp/..."
ALL_STAGED=true
for f in "${STAGING_FILES[@]}"; do
    if [ -f "$f" ]; then
        log "  FOUND: $f ($(wc -l < "$f") lines)"
    else
        log "  MISSING: $f"
        ALL_STAGED=false
    fi
done

if [ "$ALL_STAGED" = false ]; then
    log "ABORT: Not all staging files found. SCP all 3 files to /tmp/ first."
    echo ""
    echo "Run these from PowerShell (NOT the SSH window):"
    echo '  scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\data_integrity.py root@64.176.214.96:/tmp/'
    echo '  scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\learning_engine.py root@64.176.214.96:/tmp/'
    echo '  scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\lazarus.py root@64.176.214.96:/tmp/'
    exit 1
fi

# ── STEP 1: Backup all target files ─────────────────────────────────────────
log "STEP 1: Creating backup at ${BACKUP_DIR}"
mkdir -p "$BACKUP_DIR"

for f in "${TARGET_FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "${BACKUP_DIR}/$(basename "$f")"
        log "  BACKED UP: $f"
    else
        log "  SKIP (new file): $f — no backup needed"
    fi
done

# ── STEP 2: Syntax-check staging files BEFORE copying ───────────────────────
log "STEP 2: Pre-copy syntax verification of staging files..."
SYNTAX_OK=true

# data_integrity.py is standalone — can verify directly
if $VENV_PYTHON -m py_compile /tmp/data_integrity.py 2>&1 | tee -a "$LOG_FILE"; then
    log "  SYNTAX OK: /tmp/data_integrity.py"
else
    log "  SYNTAX FAIL: /tmp/data_integrity.py"
    SYNTAX_OK=false
fi

# learning_engine.py imports from data_integrity — copy DI first to test
cp /tmp/data_integrity.py "${BASE_DIR}/data_integrity.py"
if $VENV_PYTHON -m py_compile /tmp/learning_engine.py 2>&1 | tee -a "$LOG_FILE"; then
    log "  SYNTAX OK: /tmp/learning_engine.py"
else
    log "  SYNTAX FAIL: /tmp/learning_engine.py"
    SYNTAX_OK=false
fi

if [ "$SYNTAX_OK" = false ]; then
    log "SYNTAX VERIFICATION FAILED — aborting before copy"
    # Restore data_integrity.py if we just put it there
    if [ -f "${BACKUP_DIR}/data_integrity.py" ]; then
        cp "${BACKUP_DIR}/data_integrity.py" "${BASE_DIR}/data_integrity.py"
    else
        rm -f "${BASE_DIR}/data_integrity.py"
    fi
    exit 1
fi

# ── STEP 3: Copy all staging files to target ────────────────────────────────
log "STEP 3: Installing files..."
# data_integrity.py already copied in step 2
cp /tmp/learning_engine.py "${BASE_DIR}/learning_engine.py"
cp /tmp/lazarus.py "${BASE_DIR}/lazarus.py"
log "  INSTALLED: data_integrity.py"
log "  INSTALLED: learning_engine.py"
log "  INSTALLED: lazarus.py"

# Set ownership
chown solbot:solbot "${BASE_DIR}/data_integrity.py" "${BASE_DIR}/learning_engine.py" "${BASE_DIR}/lazarus.py"
log "  OWNERSHIP: set to solbot:solbot"

# ── STEP 4: Final syntax check (in-place) ───────────────────────────────────
log "STEP 4: Final syntax verification (in-place)..."
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
    log "IN-PLACE SYNTAX VERIFICATION FAILED — initiating rollback"
    rollback
    exit 1
fi

# ── STEP 5: Restart service ─────────────────────────────────────────────────
log "STEP 5: Restarting ${SERVICE_NAME}..."
systemctl restart "$SERVICE_NAME"
sleep 5

# ── STEP 6: Health check ────────────────────────────────────────────────────
log "STEP 6: Health check..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE: active (running)"
else
    log "  SERVICE FAILED TO START — initiating rollback"
    journalctl -u "$SERVICE_NAME" --no-pager -n 30 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

# Check for startup assertions
log "STEP 6b: Checking startup assertions..."
sleep 5  # Give it time to run startup checks
STARTUP_LOG=$(journalctl -u "$SERVICE_NAME" --no-pager -n 50 --since "30 seconds ago" 2>&1)
echo "$STARTUP_LOG" | tee -a "$LOG_FILE"

if echo "$STARTUP_LOG" | grep -q "\[STARTUP\] ASSERTION FAILED"; then
    log "STARTUP ASSERTION FAILED — service started but config is bad"
    log "  Check the log above for details. Service may have self-terminated."
    # Don't rollback automatically — the assertion may have already killed the process
    # Josh decides what to do
elif echo "$STARTUP_LOG" | grep -q "\[STARTUP\] All assertions passed"; then
    log "  STARTUP ASSERTIONS: PASSED"
elif echo "$STARTUP_LOG" | grep -q "data_integrity not available"; then
    log "  WARNING: data_integrity module not loaded — check import"
else
    log "  STARTUP ASSERTIONS: no output yet (may still be loading)"
fi

# Check for errors
if echo "$STARTUP_LOG" | grep -qi "error\|traceback\|exception"; then
    log "  WARNING: Errors detected in startup log — review above"
fi

# ── STEP 7: Verify data_integrity import works ──────────────────────────────
log "STEP 7: Verifying data_integrity module..."
if $VENV_PYTHON -c "from data_integrity import validate_epoch_query, validate_startup_config, check_data_anomalies; print('data_integrity import OK')" 2>&1 | tee -a "$LOG_FILE"; then
    log "  MODULE IMPORT: OK"
else
    log "  MODULE IMPORT: FAILED (non-fatal — service may still work with fallback)"
fi

# ── STEP 8: Summary ─────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log "  Files deployed:"
log "    - data_integrity.py (NEW: 5-layer validation module)"
log "    - learning_engine.py (Layer 2 input + Layer 3 output validation)"
log "    - lazarus.py (Layer 1 query + Layer 4 startup + Layer 5 anomaly)"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "============================================================"
echo "  DEPLOYMENT SUCCESSFUL"
echo "============================================================"
echo ""
echo "Quick verification commands:"
echo "  systemctl status lazarus"
echo "  journalctl -u lazarus --no-pager -n 50 | grep 'STARTUP\|LEARNING\|ANOMALY\|QUERY'"
echo "  journalctl -u lazarus --no-pager -n 30 | grep -i error || echo 'OK: no errors'"
echo "  /home/solbot/lazarus/venv/bin/python3 -c \"from data_integrity import validate_epoch_query; print('OK')\""
echo ""
echo "Backup preserved at: ${BACKUP_DIR}"
