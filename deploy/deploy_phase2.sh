#!/bin/bash
# ============================================================
# LAZARUS PHASE 2 — HIGH-VELOCITY PAPER MODE ($10k)
#
# WHAT THIS DOES:
#   1. $10,000 virtual capital for paper trades
#   2. Self-regulation DISABLED in paper mode (take every signal)
#   3. Learning engine: 20-trade Stoic gate (no config writes on noise)
#   4. Fail-closed scanner (fail = "unchecked" default)
#   5. Ghost Trap (CFG type verification at startup)
#   6. Daily loss limit disabled in paper mode
#   7. Version bump to v3.1
#
# DEPLOY:
#   PowerShell: scp -i $HOME\sol_new C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\deploy_phase2.sh root@64.176.214.96:/tmp/
#   SSH:        bash /tmp/deploy_phase2.sh
# ============================================================
set -e

DIR="/home/solbot/lazarus"
DB="$DIR/logs/lazarus.db"
TS=$(date +%Y%m%d_%H%M%S)
BK="$DIR/backup_phase2_${TS}"

echo "============================================================"
echo "  LAZARUS PHASE 2 — HIGH-VELOCITY PAPER MODE"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "============================================================"
echo ""

# ── STEP 1: BACKUP ──
echo "=== STEP 1: Backing up files ==="
mkdir -p "$BK"
cp "$DIR/lazarus.py" "$BK/"
cp "$DIR/learning_engine.py" "$BK/"
cp "$DIR/self_regulation.py" "$BK/"
echo "  Saved to: $BK"
echo ""

# ── STEP 2: STOP SERVICE ──
echo "=== STEP 2: Stopping Lazarus ==="
systemctl stop lazarus
sleep 1
echo "  Service stopped"
echo ""

# ── STEP 3: APPLY CODE PATCHES ──
echo "=== STEP 3: Applying patches ==="
cat > /tmp/phase2_patcher.py << 'PYEOF'
#!/usr/bin/env python3
"""Phase 2 patcher: 9 targeted patches across 3 files."""
import sys

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def patch(code, old, new, desc):
    if old not in code:
        print(f"  FAIL: {desc}")
        print(f"  Looking for: {repr(old[:120])}...")
        sys.exit(1)
    code = code.replace(old, new, 1)
    print(f"  OK: {desc}")
    return code

# ═════════════════════════════════════════════════════════════════════
# 1. LEARNING ENGINE — Stoic Gate (MIN_TRADES = 20)
# ═════════════════════════════════════════════════════════════════════
print("--- learning_engine.py ---")
le = read_file("/home/solbot/lazarus/learning_engine.py")

le = patch(le,
    '    if not trades:\n        print("No trades to learn from")\n        return',
    '''    MIN_TRADES_FOR_LEARNING = 20  # Stoic gate: no config writes on noise
    if not trades:
        print("No trades to learn from")
        return
    if len(trades) < MIN_TRADES_FOR_LEARNING:
        print(f"Stoic gate: {len(trades)}/{MIN_TRADES_FOR_LEARNING} trades — blacklist only")
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
        c.commit()
        return''',
    "Patch 1/9: MIN_TRADES = 20 Stoic gate")

write_file("/home/solbot/lazarus/learning_engine.py", le)

# ═════════════════════════════════════════════════════════════════════
# 2. SELF-REGULATION — minimum trades for regime evaluation
# ═════════════════════════════════════════════════════════════════════
print("\n--- self_regulation.py ---")
sr = read_file("/home/solbot/lazarus/self_regulation.py")

sr = patch(sr,
    '    if not trades:\n        return {"mode": "normal", "win_rate": 0.5, "consec_sl": 0, "reason": "no data"}',
    '''    if not trades or len(trades) < REGIME_WINDOW:
        return {"mode": "normal", "win_rate": 0.5, "consec_sl": 0,
                "reason": f"insufficient data ({len(trades) if trades else 0}/{REGIME_WINDOW} trades)"}''',
    "Patch 2/9: Minimum trade threshold for regime eval")

write_file("/home/solbot/lazarus/self_regulation.py", sr)

# ═════════════════════════════════════════════════════════════════════
# 3. LAZARUS — 7 patches
# ═════════════════════════════════════════════════════════════════════
print("\n--- lazarus.py ---")
lz = read_file("/home/solbot/lazarus/lazarus.py")

# 3a. Version bump
lz = patch(lz,
    '    log.info("  Lazarus v3.0 \u2014 Target: $20,000")',
    '    log.info("  Lazarus v3.1 \u2014 High-Velocity Paper Mode ($10k)")',
    "Patch 3/9: Version bump to v3.1")

# 3b. Ghost Trap — verify CFG types at startup
lz = patch(lz,
    'PAPER = ENV.get("PAPER_TRADING", "false").lower() == "true"',
    '''PAPER = ENV.get("PAPER_TRADING", "false").lower() == "true"
# ── GHOST TRAP: verify critical CFG types at startup ──
for _gt_key in ["min_chg_pct", "max_chg_pct", "min_liq", "stop_loss", "trail_arm", "trail_pct", "position_pct"]:
    _gt_val = CFG[_gt_key]
    if not isinstance(_gt_val, (int, float)):
        log.error(f"GHOST-TRAP TYPE POISON: CFG[{_gt_key}] = {_gt_val!r} type={type(_gt_val).__name__}")
    else:
        log.info(f"GHOST-TRAP: CFG[{_gt_key}] type={type(_gt_val).__name__} val={_gt_val}")''',
    "Patch 4/9: Ghost Trap CFG type diagnostic")

# 3c. Fail-closed scanner: unchecked default
lz = patch(lz,
    '                fail = None\n                if hourly < CFG["min_hourly_vol"]:',
    '                fail = "unchecked"  # Fail-closed: must explicitly pass\n                if hourly < CFG["min_hourly_vol"]:',
    "Patch 5/9: Fail-closed scanner default")

# 3d. Fail-closed scanner: explicit pass after primary filter chain
lz = patch(lz,
    '                elif sym in self._last_chg and c1h < self._last_chg[sym] - 5.0:\n                    fail = "chg_fading"\n                # Past-peak check',
    '                elif sym in self._last_chg and c1h < self._last_chg[sym] - 5.0:\n                    fail = "chg_fading"\n                else:\n                    fail = None  # PASSED all primary filters\n                # Past-peak check',
    "Patch 6/9: Fail-closed explicit pass")

# 3e. $10k virtual capital — starting balance
lz = patch(lz,
    '''        bal = await rpc_get_balance(session)
        log.info(f"Starting balance: {bal:.4f} SOL (~${bal * get_sol_price():.2f})")''',
    '''        bal = await rpc_get_balance(session)
        if PAPER:
            _real_bal = bal
            _sol_p = max(get_sol_price(), 1)
            bal = 10000.0 / _sol_p
            log.info(f"Starting balance: {bal:.2f} SOL (~$10,000 virtual) [real={_real_bal:.4f} SOL]")
        else:
            log.info(f"Starting balance: {bal:.4f} SOL (~${bal * get_sol_price():.2f})")''',
    "Patch 7/9: $10k virtual capital — starting balance")

# 3f. $10k virtual capital — main loop
lz = patch(lz,
    '''                bal = await rpc_get_balance(session)
                sol_price = get_sol_price()
                log.info(f"[Cycle {cycle}] {bal:.4f} SOL (${bal * sol_price:.2f}) | "
                         f"open={len(active_addrs)}/{CFG['max_positions']}")''',
    '''                bal = await rpc_get_balance(session)
                sol_price = get_sol_price()
                if PAPER:
                    bal = 10000.0 / max(sol_price, 1)  # $10k virtual capital
                log.info(f"[Cycle {cycle}] {bal:.4f} SOL (${bal * sol_price:.2f}) | "
                         f"open={len(active_addrs)}/{CFG['max_positions']}")''',
    "Patch 8/9: $10k virtual capital — main loop")

# 3g. Disable SR + daily loss limit in paper mode
#     (combined: SR heartbeat, SR scan pause, daily loss limit)

# SR heartbeat
lz = patch(lz,
    '''    if _SR:
        try:
            asyncio.create_task(SR.heartbeat_loop(60))
        except Exception:
            pass''',
    '''    if _SR and not PAPER:
        try:
            asyncio.create_task(SR.heartbeat_loop(60))
        except Exception:
            pass
    elif _SR and PAPER:
        log.info("Self-regulation DISABLED (paper mode — high-velocity data collection)")''',
    "Patch 9a/9: Disable SR heartbeat in paper mode")

# SR scan pause check
lz = patch(lz,
    '''                if _SR:
                    try:
                        if CR.is_scan_paused():
                            log.info("SCAN PAUSED by self-regulation")
                            bridge.scan_ended()
                            await asyncio.sleep(CFG["scan_interval"])
                            continue
                    except Exception:
                        pass''',
    '''                if _SR and not PAPER:
                    try:
                        if CR.is_scan_paused():
                            log.info("SCAN PAUSED by self-regulation")
                            bridge.scan_ended()
                            await asyncio.sleep(CFG["scan_interval"])
                            continue
                    except Exception:
                        pass''',
    "Patch 9b/9: Disable SR scan pause in paper mode")

# Daily loss limit
lz = patch(lz,
    '                if portfolio_usd > 0 and abs(daily_pnl) / portfolio_usd * 100 > CFG["daily_loss_limit_pct"]:',
    '                if not PAPER and portfolio_usd > 0 and abs(daily_pnl) / portfolio_usd * 100 > CFG["daily_loss_limit_pct"]:',
    "Patch 9c/9: Disable daily loss limit in paper mode")

write_file("/home/solbot/lazarus/lazarus.py", lz)

print("\n=== ALL 9 PATCHES APPLIED SUCCESSFULLY ===")
PYEOF

python3 /tmp/phase2_patcher.py
PATCH_RC=$?
rm -f /tmp/phase2_patcher.py

if [ $PATCH_RC -ne 0 ]; then
    echo ""
    echo "!!! PATCH FAILED — RESTORING BACKUPS !!!"
    cp "$BK/lazarus.py" "$DIR/"
    cp "$BK/learning_engine.py" "$DIR/"
    cp "$BK/self_regulation.py" "$DIR/"
    systemctl start lazarus
    echo "Backups restored, service restarted on old code."
    exit 1
fi
echo ""

# ── STEP 4: VERIFY SYNTAX ──
echo "=== STEP 4: Verifying Python syntax ==="
python3 -c "
import py_compile
for f in ['lazarus.py', 'learning_engine.py', 'self_regulation.py']:
    path = f'/home/solbot/lazarus/{f}'
    py_compile.compile(path, doraise=True)
    print(f'  {f}: SYNTAX OK')
"
SYNTAX_RC=$?

if [ $SYNTAX_RC -ne 0 ]; then
    echo ""
    echo "!!! SYNTAX ERROR — RESTORING BACKUPS !!!"
    cp "$BK/lazarus.py" "$DIR/"
    cp "$BK/learning_engine.py" "$DIR/"
    cp "$BK/self_regulation.py" "$DIR/"
    systemctl start lazarus
    echo "Backups restored, service restarted on old code."
    exit 1
fi
echo ""

# ── STEP 5: CLEAN DATABASE ──
echo "=== STEP 5: Cleaning database ==="
sqlite3 "$DB" "DELETE FROM dynamic_config;"
echo "  dynamic_config: CLEARED"
sqlite3 "$DB" "UPDATE bot_config SET value='normal' WHERE key='regime_mode';"
echo "  regime_mode: reset to normal"
sqlite3 "$DB" "UPDATE bot_config SET value='0' WHERE key='scan_pause_until';"
echo "  scan_pause_until: reset to 0"
echo ""

# ── STEP 6: RESTART AND VERIFY ──
echo "=== STEP 6: Restarting Lazarus ==="
systemctl start lazarus
sleep 4
echo ""
echo "=== STARTUP LOGS (look for v3.1 banner + Ghost Trap) ==="
journalctl -u lazarus --no-pager -n 30
echo ""
echo "=== DYNAMIC_CONFIG (should be empty) ==="
sqlite3 "$DB" "SELECT key, value FROM dynamic_config ORDER BY key;" 2>/dev/null || echo "(table empty)"
echo ""
echo "=== REGIME CHECK ==="
sqlite3 "$DB" "SELECT key, value FROM bot_config WHERE key IN ('regime_mode','scan_pause_until') ORDER BY key;"
echo ""

echo "============================================================"
echo "  PHASE 2 DEPLOYMENT COMPLETE"
echo ""
echo "  What changed:"
echo "    - Version: v3.1 High-Velocity Paper Mode"
echo "    - Virtual capital: \$10,000 (sizes off ~100 SOL)"
echo "    - Self-regulation: DISABLED in paper mode"
echo "    - Daily loss limit: DISABLED in paper mode"
echo "    - Learning engine: 20-trade Stoic gate"
echo "    - Scanner: Fail-closed (unchecked default)"
echo "    - Ghost Trap: CFG type verification at startup"
echo ""
echo "  What to watch for in logs:"
echo "    - Banner: 'Lazarus v3.1 — High-Velocity Paper Mode'"
echo "    - Balance: ~100 SOL (\$10,000 virtual)"
echo "    - GHOST-TRAP lines confirming type=float"
echo "    - NO 'SCAN PAUSED' or 'PAUSE TRADING' messages"
echo "    - Candidates should flow when market wakes up"
echo ""
echo "  Backup: $BK"
echo "============================================================"
