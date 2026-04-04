#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment Template — Hardened Fortress Protocol
# ══════════════════════════════════════════════════════════════════════════════
#
# USAGE:
#   1. Copy this template for each new patch
#   2. Fill in the PATCH DEFINITIONS section with your find/replace pairs
#   3. SCP to server from PowerShell:
#        scp -i $HOME\sol_new lazarus_deploy_PATCHNAME.sh root@64.176.214.96:/tmp/
#   4. SSH in and run:
#        bash /tmp/lazarus_deploy_PATCHNAME.sh
#
# SAFETY GUARANTEES:
#   - Timestamped backup of ALL target files before any writes
#   - Atomic rollback if ANY py_compile check fails
#   - Automatic service restart with health verification
#   - If service fails to start, files are restored and service restarted
#   - Full audit log written to /home/solbot/lazarus/logs/deploys/
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── CONFIG ───────────────────────────────────────────────────────────────────
PATCH_NAME="CHANGEME"           # Short name for this patch (e.g., "epoch_format_fix")
VENV_PYTHON="/home/solbot/lazarus/venv/bin/python3"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
LOG_DIR="${BASE_DIR}/logs/deploys"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"

# ── TARGET FILES (add all files this patch touches) ──────────────────────────
TARGET_FILES=(
    "${BASE_DIR}/lazarus.py"
    "${BASE_DIR}/learning_engine.py"
    "${BASE_DIR}/self_regulation.py"
)

# ══════════════════════════════════════════════════════════════════════════════
# PATCH DEFINITIONS — edit this function for each new patch
# ══════════════════════════════════════════════════════════════════════════════
apply_patches() {
    # Each patch is a python3 -c command that reads a file, replaces a string,
    # and writes it back. Add as many as needed.
    #
    # TEMPLATE (copy and modify):
    #   python3 -c "
    #   f='${BASE_DIR}/FILENAME.py'
    #   s=open(f).read()
    #   old='OLD STRING HERE'
    #   new='NEW STRING HERE'
    #   assert old in s, f'PATCH FAILED: old string not found in {f}'
    #   open(f,'w').write(s.replace(old, new))
    #   print(f'  PATCHED {f}: replaced [{old[:50]}...]')
    #   "
    #
    # ── EXAMPLE (epoch format fix) ───────────────────────────────────────────
    # python3 -c "
    # f='${BASE_DIR}/learning_engine.py'
    # s=open(f).read()
    # old='V3_EPOCH = \"2026-03-29 17:44:00\"'
    # new='V3_EPOCH = \"2026-03-29T17:44:00\"'
    # assert old in s, f'PATCH FAILED: old string not found in {f}'
    # open(f,'w').write(s.replace(old, new))
    # print(f'  PATCHED {f}')
    # "

    echo "ERROR: No patches defined. Edit apply_patches() in this script."
    return 1
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

# ── STEP 2: Apply patches ────────────────────────────────────────────────────
log "STEP 2: Applying patches..."
if ! apply_patches 2>&1 | tee -a "$LOG_FILE"; then
    log "PATCH APPLICATION FAILED"
    rollback
    exit 1
fi

# ── STEP 3: Syntax verification ──────────────────────────────────────────────
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

# ── STEP 4: Restart service ──────────────────────────────────────────────────
log "STEP 4: Restarting ${SERVICE_NAME}..."
systemctl restart "$SERVICE_NAME"
sleep 3

# ── STEP 5: Health check ─────────────────────────────────────────────────────
log "STEP 5: Health check..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  SERVICE: active (running) ✓"
    # Grab first few lines of output to confirm clean startup
    journalctl -u "$SERVICE_NAME" --no-pager -n 5 --since "30 seconds ago" 2>&1 | tee -a "$LOG_FILE"
else
    log "  SERVICE FAILED TO START — initiating rollback"
    # Capture error output for diagnosis
    journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "60 seconds ago" 2>&1 | tee -a "$LOG_FILE"
    rollback
    exit 1
fi

# ── STEP 6: Summary ──────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "✓ Deployment successful. Backup preserved at: ${BACKUP_DIR}"
