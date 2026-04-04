#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  LAZARUS PHASE 2 FIX"
echo "  $(date -u +'%Y-%m-%d %H:%M UTC')"
echo "============================================================"

BACKUP="/home/solbot/lazarus/backup_phase2fix_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
cp /home/solbot/lazarus/lazarus.py "$BACKUP/"
echo "=== Backed up to $BACKUP ==="

systemctl stop lazarus 2>/dev/null || true
echo "=== Service stopped ==="

echo "=== Applying fixes ==="
/home/solbot/lazarus/venv/bin/python3 << 'PYEOF'
import re, sys

path = "/home/solbot/lazarus/lazarus.py"
with open(path, "r") as f:
    code = f.read()

ok = 0
fail = 0

def patch(name, old, new):
    global code, ok, fail
    if old in code:
        code = code.replace(old, new, 1)
        print(f"  OK: {name}")
        ok += 1
    else:
        print(f"  FAIL: {name}")
        print(f"    Looking for: {repr(old[:100])}...")
        fail += 1

patch("Fix 1/5: Revert fail=unchecked (truthy bug)",
    'fail = "unchecked"',
    'fail = None')

patch("Fix 2/5: Virtual $10k balance (startup)",
    '        bal = await rpc_get_balance(session)\n        log.info(f"Starting balance: {bal:.4f} SOL (~${bal * get_sol_price():.2f})")',
    '        bal = await rpc_get_balance(session)\n        if PAPER:\n            bal = 10_000 / max(get_sol_price(), 1)\n            log.info(f"Starting balance: {bal:.4f} SOL (~$10,000 VIRTUAL)")\n        else:\n            log.info(f"Starting balance: {bal:.4f} SOL (~${bal * get_sol_price():.2f})")')

patch("Fix 3/5: Virtual balance (loop override)",
    '                bal = await rpc_get_balance(session)\n                sol_price = get_sol_price()',
    '                bal = await rpc_get_balance(session)\n                if PAPER:\n                    bal = 10_000 / max(get_sol_price(), 1)\n                sol_price = get_sol_price()')

patch("Fix 4/5: SR pause skipped in paper mode",
    '                if _SR:\n                    try:\n                        if CR.is_scan_paused():',
    '                if _SR and not PAPER:\n                    try:\n                        if CR.is_scan_paused():')

m = re.search(r'log\.info\("  Lazarus v3\.[^"]*"\)', code)
if m:
    code = code.replace(m.group(), 'log.info("  Lazarus v3.1 \u2014 High-Velocity Paper Mode ($10k)")', 1)
    print(f"  OK: Fix 5/5: Version string updated")
    ok += 1
else:
    print(f"  FAIL: Fix 5/5: Version string not found")
    fail += 1

with open(path, "w") as f:
    f.write(code)

print(f"\n  Results: {ok} OK, {fail} FAIL")
if fail > 0:
    sys.exit(1)
PYEOF

PATCH_RESULT=$?
if [ $PATCH_RESULT -ne 0 ]; then
    echo "!!! PATCH FAILED — rolling back !!!"
    cp "$BACKUP/lazarus.py" /home/solbot/lazarus/lazarus.py
    systemctl start lazarus
    exit 1
fi

echo ""
echo "=== Syntax check ==="
/home/solbot/lazarus/venv/bin/python3 -m py_compile /home/solbot/lazarus/lazarus.py
if [ $? -eq 0 ]; then
    echo "  lazarus.py: SYNTAX OK"
else
    echo "!!! SYNTAX FAIL — rolling back !!!"
    cp "$BACKUP/lazarus.py" /home/solbot/lazarus/lazarus.py
    systemctl start lazarus
    exit 1
fi

echo ""
echo "=== DB cleanup ==="
sqlite3 /home/solbot/lazarus/logs/lazarus.db "DELETE FROM dynamic_config; DELETE FROM bot_config WHERE key='scan_pause_until'; DELETE FROM bot_config WHERE key='regime_mode';"
echo "  Cleared: dynamic_config, scan_pause_until, regime_mode"

echo ""
echo "=== Restarting Lazarus ==="
systemctl start lazarus
sleep 3
echo ""
echo "=== Startup logs ==="
journalctl -u lazarus --no-pager -n 25
echo ""
echo "============================================================"
echo "  PHASE 2 FIX COMPLETE"
echo "============================================================"
