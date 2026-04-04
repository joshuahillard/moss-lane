#!/bin/bash
# ============================================================
# Moss Lane — Epoch Filter Deployment
# Prevents Lazarus learning engine + self-regulation from
# using pre-v3 trade data (the "time-travel bug")
#
# WHAT IT DOES:
#   1. Backs up current learning_engine.py and self_regulation.py
#   2. Patches both files to add V3_EPOCH timestamp filter
#   3. Verifies Python syntax on both patched files
#   4. Restarts the lazarus service
#
# EPOCH: 2026-03-28T04:53:00 (v3 deployment timestamp)
# ============================================================

set -e
LAZARUS_DIR="/home/solbot/lazarus"
BACKUP_DIR="${LAZARUS_DIR}/backup_epoch_$(date +%Y%m%d_%H%M%S)"
EPOCH="2026-03-28T04:53:00"

echo "============================================================"
echo "  Moss Lane — Epoch Filter Deployment"
echo "  Epoch cutoff: ${EPOCH}"
echo "============================================================"
echo ""

# ── Step 1: Backup ──
echo ">>> Step 1: Backing up current files..."
mkdir -p "$BACKUP_DIR"
cp "${LAZARUS_DIR}/learning_engine.py" "${BACKUP_DIR}/learning_engine.py"
cp "${LAZARUS_DIR}/self_regulation.py" "${BACKUP_DIR}/self_regulation.py"
echo "    Backed up to: ${BACKUP_DIR}"
echo ""

# ── Step 2: Patch learning_engine.py ──
echo ">>> Step 2: Patching learning_engine.py..."

python3 << 'PYEOF'
import re

filepath = "/home/solbot/lazarus/learning_engine.py"
epoch = "2026-03-28T04:53:00"

with open(filepath, "r") as f:
    content = f.read()

# --- Add V3_EPOCH constant after imports (if not already present) ---
if "V3_EPOCH" not in content:
    # Find the last import line and insert after it
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_idx = i + 1
    lines.insert(insert_idx, "")
    lines.insert(insert_idx + 1, f'V3_EPOCH = "{epoch}"  # Only learn from v3 trades')
    content = "\n".join(lines)
    print("    Added V3_EPOCH constant")

# --- Patch the main trades query in analyze_and_tune() ---
# Original: FROM trades\n        ORDER BY timestamp DESC LIMIT 50
# New:      FROM trades WHERE timestamp >= V3_EPOCH\n        ORDER BY timestamp DESC LIMIT 50

old_query = """FROM trades
        ORDER BY timestamp DESC LIMIT 50"""
new_query = """FROM trades WHERE timestamp >= ?
        ORDER BY timestamp DESC LIMIT 50
    """.rstrip()

if "WHERE timestamp >= ?" not in content.split("analyze_and_tune")[1].split("def ")[0] if "analyze_and_tune" in content else "":
    content = content.replace(old_query, new_query, 1)
    # Also need to pass the epoch parameter to execute()
    content = content.replace(
        '""").fetchall()',
        '""", (V3_EPOCH,)).fetchall()',
        1
    )
    print("    Patched analyze_and_tune() query")
else:
    print("    analyze_and_tune() already patched")

with open(filepath, "w") as f:
    f.write(content)

print("    learning_engine.py updated")
PYEOF

echo ""

# ── Step 3: Patch self_regulation.py ──
echo ">>> Step 3: Patching self_regulation.py..."

python3 << 'PYEOF'
import re

filepath = "/home/solbot/lazarus/self_regulation.py"
epoch = "2026-03-28T04:53:00"

with open(filepath, "r") as f:
    content = f.read()

# --- Add V3_EPOCH constant after imports (if not already present) ---
if "V3_EPOCH" not in content:
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_idx = i + 1
    lines.insert(insert_idx, "")
    lines.insert(insert_idx + 1, f'V3_EPOCH = "{epoch}"  # Only evaluate v3 trades for regime')
    content = "\n".join(lines)
    print("    Added V3_EPOCH constant")

# --- Patch _get_recent_trades() ---
# Original: "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?"
# New:      "SELECT * FROM trades WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?"

old_query = '"SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?"'
new_query = '"SELECT * FROM trades WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?"'

if old_query in content:
    content = content.replace(old_query, new_query, 1)
    # Also update the parameter tuple
    content = content.replace(
        "(n,)",
        "(V3_EPOCH, n,)",
        1
    )
    print("    Patched _get_recent_trades() query")
else:
    print("    _get_recent_trades() already patched or different format")

with open(filepath, "w") as f:
    f.write(content)

print("    self_regulation.py updated")
PYEOF

echo ""

# ── Step 4: Verify syntax ──
echo ">>> Step 4: Verifying Python syntax..."
echo -n "    learning_engine.py: "
if python3 -m py_compile "${LAZARUS_DIR}/learning_engine.py" 2>&1; then
    echo "OK"
else
    echo "SYNTAX ERROR — rolling back!"
    cp "${BACKUP_DIR}/learning_engine.py" "${LAZARUS_DIR}/learning_engine.py"
    echo "    Restored from backup."
    exit 1
fi

echo -n "    self_regulation.py: "
if python3 -m py_compile "${LAZARUS_DIR}/self_regulation.py" 2>&1; then
    echo "OK"
else
    echo "SYNTAX ERROR — rolling back!"
    cp "${BACKUP_DIR}/self_regulation.py" "${LAZARUS_DIR}/self_regulation.py"
    echo "    Restored from backup."
    exit 1
fi
echo ""

# ── Step 5: Restart Lazarus ──
echo ">>> Step 5: Restarting Lazarus..."
systemctl restart lazarus
sleep 3

# ── Step 6: Verify ──
echo ">>> Step 6: Verifying deployment..."
echo ""
echo "--- Service Status ---"
systemctl status lazarus --no-pager | head -6
echo ""
echo "--- First 10 log lines ---"
journalctl -u lazarus --no-pager -n 10
echo ""
echo "--- Epoch constant check ---"
grep "V3_EPOCH" "${LAZARUS_DIR}/learning_engine.py" | head -1
grep "V3_EPOCH" "${LAZARUS_DIR}/self_regulation.py" | head -1
echo ""
echo "--- Dynamic config (should be empty) ---"
sqlite3 "${LAZARUS_DIR}/logs/lazarus.db" "SELECT * FROM dynamic_config;"
echo ""
echo "============================================================"
echo "  Epoch filter deployed successfully!"
echo "  Learning engine + self-regulation now ignore pre-v3 trades"
echo "  Backup: ${BACKUP_DIR}"
echo "============================================================"
