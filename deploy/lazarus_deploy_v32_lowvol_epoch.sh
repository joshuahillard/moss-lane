#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Deployment: v3.2 Low-Volume Epoch
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Apply the April 15, 2026 low-volume epoch experiment on the VPS without
#   hand-editing the live engine.
#
# WINDOWS FLOW:
#   PowerShell:
#     scp -i $HOME\sol_new "C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo\deploy\lazarus_deploy_v32_lowvol_epoch.sh" root@64.176.214.96:/tmp/
#
#   SSH window:
#     bash /tmp/lazarus_deploy_v32_lowvol_epoch.sh
#
# PROFILE:
#   min_hourly_vol = 250
#   min_chg_pct    = 10.0
#   max_chg_pct    = 120.0
#   min_liq        = 30000
#   min_vmr        = 0.10
#   filter_regime  = v3.2_lowvol_epoch
#
# ROLLBACK RULE:
#   Monitor for 2 hours after deploy. If there are zero non-zero candidate
#   cycles and the filter breakdown shape is still effectively frozen
#   (<= 2 unique breakdown lines), auto-restore the backed-up code and DB.
#
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PATCH_NAME="v32_lowvol_epoch"
VENV_PYTHON="/home/solbot/lazarus/venv/bin/python3"
SERVICE_NAME="lazarus"
BASE_DIR="/home/solbot/lazarus"
DB_PATH="${BASE_DIR}/logs/lazarus.db"
ENV_PATH="${BASE_DIR}/.env"
TARGET_FILE="${BASE_DIR}/lazarus.py"
LOG_DIR="${BASE_DIR}/logs/deploys"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BASE_DIR}/backup_${PATCH_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/deploy_${PATCH_NAME}_${TIMESTAMP}.log"
MONITOR_SECONDS=$((2 * 60 * 60))
TARGET_FILTER_LINE="Runtime filters: vol >=250 | chg 10.0-120.0% | liq >=\$30,000 | regime v3.2_lowvol_epoch"

TARGET_FILES=(
    "${BASE_DIR}/lazarus.py"
)

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
    sleep 4

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
        log "ABORT: PAPER_TRADING is not true in ${ENV_PATH}. This experiment is paper-only."
        exit 1
    fi

    log "PRE-FLIGHT: PAPER_TRADING=true confirmed."
}

apply_patches() {
    python3 - <<'PY'
from pathlib import Path
import re

target = Path("/home/solbot/lazarus/lazarus.py")
s = target.read_text()
original = s

replacements = [
    (r'("min_hourly_vol":\s*)(\d+)', r'\g<1>250'),
    (r'("min_chg_pct":\s*)([0-9.]+)', r'\g<1>10.0'),
    (r'("max_chg_pct":\s*)([0-9.]+)', r'\g<1>120.0'),
    (r'("min_liq":\s*)([0-9_]+)', r'\g<1>30_000'),
    (r'("min_vmr":\s*)([0-9.]+)', r'\g<1>0.10'),
]

for pattern, repl in replacements:
    s, count = re.subn(pattern, repl, s, count=1)
    if count == 0:
        raise SystemExit(f"PATCH FAILED: pattern not found: {pattern}")

if '"filter_regime":' not in s:
    s, count = re.subn(
        r'("min_vmr":\s*0\.10,\s*# volume-to-MC ratio floor\n)',
        r'\1    "filter_regime":    "v3.2_lowvol_epoch",  # persisted on trade rows for cohort analysis\n',
        s,
        count=1,
    )
    if count == 0:
        raise SystemExit("PATCH FAILED: could not insert filter_regime CFG key")
else:
    s, count = re.subn(
        r'("filter_regime":\s*")[^"]+(".*)',
        r'\1v3.2_lowvol_epoch\2',
        s,
        count=1,
    )
    if count == 0:
        raise SystemExit("PATCH FAILED: could not update filter_regime CFG key")

helper = '''
STARTUP_OVERRIDE_KEYS = {
    "position_pct",
    "max_positions",
    "take_profit",
    "stop_loss",
    "trail_arm",
    "min_hourly_vol",
    "min_chg_pct",
    "max_chg_pct",
    "min_liq",
    "min_vmr",
    "filter_regime",
}


def _coerce_cfg_value(key: str, raw: str):
    current = CFG[key]
    if isinstance(current, bool):
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int) and not isinstance(current, bool):
        return int(float(raw))
    if isinstance(current, float):
        return float(raw)
    return str(raw)


def _apply_startup_config_overrides():
    """Apply bot_config and dynamic_config before the startup banner is emitted."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            sources = (
                ("bot_config", conn.execute("SELECT key, value FROM bot_config").fetchall()),
                ("dynamic_config", conn.execute("SELECT key, value FROM dynamic_config").fetchall()),
            )
        finally:
            conn.close()

        for source_name, rows in sources:
            for key, value in rows:
                if key not in STARTUP_OVERRIDE_KEYS:
                    continue
                try:
                    CFG[key] = _coerce_cfg_value(key, value)
                    log.info(f"Startup config: {key}={CFG[key]} ({source_name})")
                except Exception as e:
                    log.warning(f"Startup config parse failed for {key}={value!r}: {e}")
    except Exception as e:
        log.warning(f"Startup config override load failed: {e}")
'''

if "_apply_startup_config_overrides()" not in s:
    anchor = 'PAPER = ENV.get("PAPER_TRADING", "false").lower() == "true"\n'
    if anchor not in s:
        raise SystemExit("PATCH FAILED: PAPER anchor not found")
    s = s.replace(anchor, anchor + "\n" + helper + "\n", 1)

schema_old = 'tx_buy TEXT, tx_sell TEXT, peak_pnl_pct REAL'
schema_new = "tx_buy TEXT, tx_sell TEXT, peak_pnl_pct REAL,\n                filter_regime TEXT DEFAULT 'unknown'"
if "filter_regime TEXT DEFAULT 'unknown'" not in s:
    if schema_old not in s:
        raise SystemExit("PATCH FAILED: trades schema anchor not found")
    s = s.replace(schema_old, schema_new, 1)

insert_old = '''hour_utc, day_of_week, address, entry, tx_buy, tx_sell, peak_pnl_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
insert_new = '''hour_utc, day_of_week, address, entry, tx_buy, tx_sell, peak_pnl_pct,
                 filter_regime)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
if "filter_regime)" not in s:
    if insert_old not in s:
        raise SystemExit("PATCH FAILED: trades INSERT anchor not found")
    s = s.replace(insert_old, insert_new, 1)

tuple_patterns = [
    (
        r'tx_buy,\s*tx_sell,\s*kwargs\.get\("peak_pnl_pct"\)\)\)',
        'tx_buy, tx_sell, kwargs.get("peak_pnl_pct"),\n                 kwargs.get("filter_regime", CFG.get("filter_regime", "unknown"))))',
    ),
    (
        r'tx_buy,\s*tx_sell,\s*kwargs\.get\("peak_pnl_pct"\),\s*"original".*?wide_net_v1"\)\)',
        'tx_buy, tx_sell, kwargs.get("peak_pnl_pct"),\n                 kwargs.get("filter_regime", CFG.get("filter_regime", "unknown"))))',
    ),
]

if 'kwargs.get("filter_regime", CFG.get("filter_regime", "unknown"))' not in s:
    replaced = False
    for pattern, repl in tuple_patterns:
        s2, count = re.subn(pattern, repl, s, count=1, flags=re.S)
        if count:
            s = s2
            replaced = True
            break
    if not replaced:
        raise SystemExit("PATCH FAILED: trades tuple anchor not found")

call_old = '            smart_money=sig.source.startswith("copy_"),\n            peak_pnl_pct=peak_pnl_pct)'
call_new = '            smart_money=sig.source.startswith("copy_"),\n            peak_pnl_pct=peak_pnl_pct,\n            filter_regime=CFG["filter_regime"])'
if 'filter_regime=CFG["filter_regime"]' not in s:
    if call_old not in s:
        raise SystemExit("PATCH FAILED: record_trade call anchor not found")
    s = s.replace(call_old, call_new, 1)

if '_apply_startup_config_overrides()' not in s.split("async def main():", 1)[1]:
    s = s.replace("async def main():\n", "async def main():\n    _apply_startup_config_overrides()\n\n", 1)

runtime_line = '    log.info(f"  Runtime filters: vol >={CFG[\'min_hourly_vol\']:.0f} | chg {CFG[\'min_chg_pct\']}-{CFG[\'max_chg_pct\']}% | liq >${CFG[\'min_liq\']:,.0f} | regime {CFG[\'filter_regime\']}")\n'
if "Runtime filters:" not in s:
    banner_anchor = '    log.info(f"  Mode   : {\'PAPER\' if PAPER else \'LIVE\'}")\n'
    if banner_anchor not in s:
        raise SystemExit("PATCH FAILED: startup banner anchor not found")
    s = s.replace(banner_anchor, banner_anchor + runtime_line, 1)
else:
    s = re.sub(
        r'^\s*log\.info\(f"  Runtime filters:.*$',
        '    log.info(f"  Runtime filters: vol >={CFG[\'min_hourly_vol\']:.0f} | chg {CFG[\'min_chg_pct\']}-{CFG[\'max_chg_pct\']}% | liq >${CFG[\'min_liq\']:,.0f} | regime {CFG[\'filter_regime\']}")',
        s,
        count=1,
        flags=re.M,
    )

cycle_runtime = '''            if cycle == 1 or cycle % 30 == 0:
                log.info(
                    f"Runtime filters: vol >={CFG['min_hourly_vol']:.0f} | "
                    f"chg {CFG['min_chg_pct']}-{CFG['max_chg_pct']}% | "
                    f"liq >${CFG['min_liq']:,.0f} | regime {CFG['filter_regime']}"
                )
'''
if "if cycle == 1 or cycle % 30 == 0:" not in s:
    anchor = "            cycle += 1\n"
    if anchor not in s:
        raise SystemExit("PATCH FAILED: cycle anchor not found")
    s = s.replace(anchor, anchor + cycle_runtime, 1)

if s == original:
    raise SystemExit("PATCH FAILED: no changes applied")

target.write_text(s)
print("  PATCHED: lazarus.py for v3.2 low-volume epoch")
PY

    if ! sqlite3 "$DB_PATH" "PRAGMA table_info(trades);" | grep -F "|filter_regime|" >/dev/null; then
        sqlite3 "$DB_PATH" "ALTER TABLE trades ADD COLUMN filter_regime TEXT DEFAULT 'unknown';"
        echo "  DB: added trades.filter_regime column"
    else
        echo "  DB: trades.filter_regime column already present"
    fi
}

update_runtime_db() {
    local epoch_ts
    epoch_ts="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"

    sqlite3 "$DB_PATH" <<SQL
BEGIN IMMEDIATE;
INSERT OR REPLACE INTO bot_config (key, value, updated_at, reason) VALUES
('min_hourly_vol', '250', '${epoch_ts}', 'v3.2 low-volume epoch'),
('min_chg_pct', '10.0', '${epoch_ts}', 'v3.2 low-volume epoch'),
('max_chg_pct', '120.0', '${epoch_ts}', 'v3.2 low-volume epoch'),
('min_liq', '30000', '${epoch_ts}', 'v3.2 low-volume epoch'),
('min_vmr', '0.10', '${epoch_ts}', 'v3.2 low-volume epoch'),
('epoch_v32_lowvol', '${epoch_ts}', '${epoch_ts}', 'v3.2 low-volume epoch start'),
('filter_regime', 'v3.2_lowvol_epoch', '${epoch_ts}', 'default trade cohort for v3.2 low-volume epoch');
DELETE FROM dynamic_config
WHERE key IN ('min_hourly_vol', 'min_chg_pct', 'max_chg_pct', 'min_liq', 'min_vmr');
COMMIT;
SQL

    log "  DB: runtime config updated for v3.2 low-volume epoch (${epoch_ts})"
}

monitor_post_deploy() {
    local monitor_start_human monitor_start_unix monitor_end now
    local logs nonzero unique_breakdowns breakdown_samples

    monitor_start_human="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    monitor_start_unix="$(date +%s)"
    monitor_end=$((monitor_start_unix + MONITOR_SECONDS))

    log "STEP 7: Monitoring for 2 hours (${monitor_start_human} -> $(date -u -d "@${monitor_end}" '+%Y-%m-%d %H:%M:%S UTC'))"

    while true; do
        now="$(date +%s)"
        if [ "$now" -ge "$monitor_end" ]; then
            break
        fi

        if journalctl -u "$SERVICE_NAME" --since "@${monitor_start_unix}" --no-pager | grep -E "Traceback|Main loop error|SyntaxError|NameError|TypeError|AttributeError" >/dev/null; then
            log "  MONITOR: Python exception detected during watch window"
            rollback
            exit 1
        fi

        sleep 60
    done

    logs="$(journalctl -u "$SERVICE_NAME" --since "@${monitor_start_unix}" --no-pager)"
    nonzero="$(printf "%s\n" "$logs" | grep -cE 'DexScreener candidates: [1-9][0-9]*' || true)"
    unique_breakdowns="$(printf "%s\n" "$logs" | grep 'Filter breakdown' | sed 's/^.*Filter breakdown/Filter breakdown/' | sort -u | sed '/^$/d' | wc -l | tr -d ' ')"
    breakdown_samples="$(printf "%s\n" "$logs" | grep 'Filter breakdown' | sed 's/^.*Filter breakdown/Filter breakdown/' | sort -u | head -5 || true)"

    log "  MONITOR: non-zero candidate cycles in 2h window = ${nonzero}"
    log "  MONITOR: unique filter breakdown lines = ${unique_breakdowns:-0}"
    if [ -n "$breakdown_samples" ]; then
        printf '%s\n' "$breakdown_samples" | tee -a "$LOG_FILE"
    fi

    if [ "${nonzero}" -eq 0 ] && [ "${unique_breakdowns:-0}" -le 2 ]; then
        log "  MONITOR: zero candidates and frozen breakdown shape — auto-rollback"
        rollback
        exit 1
    fi

    log "  MONITOR: watch window completed without rollback trigger"
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

log "PRE-FLIGHT: Current runtime filter values"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr','filter_regime')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "STEP 2: Applying code patch"
if ! apply_patches 2>&1 | tee -a "$LOG_FILE"; then
    log "PATCH APPLICATION FAILED"
    rollback
    exit 1
fi

log "STEP 3: Updating bot_config and clearing filter-key dynamic overrides"
if ! update_runtime_db 2>&1 | tee -a "$LOG_FILE"; then
    log "DB UPDATE FAILED"
    rollback
    exit 1
fi

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
journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "90 seconds ago" 2>&1 | tee -a "$LOG_FILE"

if ! journalctl -u "$SERVICE_NAME" --no-pager -n 60 --since "120 seconds ago" | grep -F "$TARGET_FILTER_LINE" >/dev/null; then
    log "  HEALTH CHECK FAILED: runtime threshold banner not found"
    rollback
    exit 1
fi

if ! journalctl -u "$SERVICE_NAME" --no-pager -n 60 --since "120 seconds ago" | grep -F "DexScreener candidates:" >/dev/null; then
    log "  HEALTH CHECK FAILED: candidate logging not observed after restart"
    rollback
    exit 1
fi

if journalctl -u "$SERVICE_NAME" --no-pager -n 60 --since "120 seconds ago" | grep -E "Traceback|Main loop error|SyntaxError|NameError|TypeError|AttributeError" >/dev/null; then
    log "  HEALTH CHECK FAILED: Python exception detected after restart"
    rollback
    exit 1
fi

log "  HEALTH CHECK: startup banner, candidate logs, and exception scan passed"

monitor_post_deploy

log "STEP 8: Post-deploy verification"
grep -n "min_hourly_vol\|min_chg_pct\|max_chg_pct\|min_liq\|min_vmr\|filter_regime" "$TARGET_FILE" | head -6 | tee -a "$LOG_FILE"
sqlite3 "$DB_PATH" "
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr','epoch_v32_lowvol','filter_regime')
ORDER BY key;
" 2>&1 | tee -a "$LOG_FILE"

log "  Backup: ${BACKUP_DIR}"
log "  Log:    ${LOG_FILE}"
log "════════════════════════════════════════════════════════════════"
log "DEPLOY COMPLETE: ${PATCH_NAME}"
log "════════════════════════════════════════════════════════════════"

echo ""
echo "v3.2 low-volume epoch deploy completed."
