#!/bin/bash
# ============================================================
# Lazarus Patch: Learning Engine Minimum Trade Threshold
# Prevents dynamic_config writes until 10+ v3 trades exist
# ============================================================
set -e

FILE="/home/solbot/lazarus/learning_engine.py"
BACKUP="/home/solbot/lazarus/learning_engine.py.bak_$(date +%Y%m%d_%H%M%S)"

echo "=== Patching learning_engine.py ==="

# Backup first
cp "$FILE" "$BACKUP"
echo "Backup saved to: $BACKUP"

# Patch: Replace the early return block with a minimum trade check
python3 << 'PYEOF'
import re

with open("/home/solbot/lazarus/learning_engine.py", "r") as f:
    code = f.read()

# 1. Replace the "No trades to learn from" block to also check minimum count
old_block = '''    if not trades:
        print("No trades to learn from")
        return'''

new_block = '''    MIN_TRADES = 10  # Don't tune config on tiny samples
    if not trades:
        print("No trades to learn from")
        return
    if len(trades) < MIN_TRADES:
        print(f"Only {len(trades)} trades — need {MIN_TRADES} before tuning config")
        # Still do blacklist checks, but skip config writes
        _blacklist_rugs(c, trades)
        c.commit()
        return'''

if old_block not in code:
    print("ERROR: Could not find target block for min trades patch")
    exit(1)

code = code.replace(old_block, new_block)

# 2. Extract the blacklist logic into its own function so it can be called independently
old_blacklist = '''    # ── Auto-blacklist: only confirmed rugs (> 15% loss), not normal SLs ──
    for t in losses:
        pnl = t[2] or 0
        exit_reason = t[6] or ""
        addr = t[1]
        if pnl < -15.0 and addr and exit_reason in ("emergency_rug", "hard_floor", "stop_loss"):
            c.execute("""
                INSERT OR REPLACE INTO rug_blacklist (address, symbol, ts, loss_pct)
                VALUES (?,?,?,?)
            """, (addr, t[0], now, pnl))
            print(f"  BLACKLISTED: {t[0]} ({pnl:.1f}%) — {exit_reason}")'''

new_blacklist = '''    # ── Auto-blacklist: only confirmed rugs (> 15% loss), not normal SLs ──
    _blacklist_rugs(c, trades)'''

if old_blacklist not in code:
    print("ERROR: Could not find blacklist block")
    exit(1)

code = code.replace(old_blacklist, new_blacklist)

# 3. Add the standalone blacklist function before _set_config
blacklist_func = '''def _blacklist_rugs(c, trades):
    """Auto-blacklist tokens with > 15% loss (confirmed rugs, not normal SLs)."""
    now = datetime.now(timezone.utc).isoformat()
    losses = [t for t in trades if (t[2] or 0) <= 0]
    for t in losses:
        pnl = t[2] or 0
        exit_reason = t[6] or ""
        addr = t[1]
        if pnl < -15.0 and addr and exit_reason in ("emergency_rug", "hard_floor", "stop_loss"):
            c.execute("""
                INSERT OR REPLACE INTO rug_blacklist (address, symbol, ts, loss_pct)
                VALUES (?,?,?,?)
            """, (addr, t[0], now, pnl))
            print(f"  BLACKLISTED: {t[0]} ({pnl:.1f}%) — {exit_reason}")

'''

old_set_config = 'def _set_config(c, key, value, reason, now):'
if old_set_config not in code:
    print("ERROR: Could not find _set_config function")
    exit(1)

code = code.replace(old_set_config, blacklist_func + old_set_config)

with open("/home/solbot/lazarus/learning_engine.py", "w") as f:
    f.write(code)

print("SUCCESS: learning_engine.py patched")
PYEOF

# Verify syntax
echo ""
echo "=== Verifying Python syntax ==="
python3 -c "
import py_compile
py_compile.compile('/home/solbot/lazarus/learning_engine.py', doraise=True)
print('SYNTAX OK')
"

# Clear dynamic_config again (in case it ran between our fix and now)
echo ""
echo "=== Clearing dynamic_config ==="
sqlite3 /home/solbot/lazarus/logs/lazarus.db "DELETE FROM dynamic_config;"
echo "dynamic_config cleared"

# Restart
echo ""
echo "=== Restarting Lazarus ==="
systemctl restart lazarus
sleep 2
journalctl -u lazarus --no-pager -n 10

echo ""
echo "============================================================"
echo "  PATCH COMPLETE"
echo "  Learning engine will NOT write config until 10+ v3 trades"
echo "  Rug blacklisting still works immediately"
echo "============================================================"
