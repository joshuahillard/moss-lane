#!/usr/bin/env bash
###############################################################################
#  MOSS LANE REBRAND SCRIPT
#  Renames Sol-Fortress → Lazarus on the server
#  - Directory: /home/solbot/fortress → /home/solbot/lazarus
#  - Main bot: fort_v2.py → lazarus.py
#  - Database: fortress.db → lazarus.db
#  - Log: fort_v2.log → lazarus.log
#  - Services: sol-fortress-v2 → lazarus, sol-fortress-dashboard → lazarus-dashboard
#  - Internal references in Python files
###############################################################################
set -euo pipefail

echo "========================================="
echo "  MOSS LANE REBRAND"
echo "  Sol-Fortress → Lazarus"
echo "========================================="
echo ""

# ---------- safety checks ----------
if [ "$(whoami)" != "root" ]; then
  echo "ERROR: Must run as root"; exit 1
fi

if [ ! -d /home/solbot/fortress ]; then
  echo "ERROR: /home/solbot/fortress not found"; exit 1
fi

# ---------- step 1: stop services ----------
echo "[1/8] Stopping services..."
systemctl stop sol-fortress-v2 2>/dev/null || true
systemctl stop sol-fortress-dashboard 2>/dev/null || true
sleep 2
echo "       Services stopped."

# ---------- step 2: rename main bot file ----------
echo "[2/8] Renaming fort_v2.py → lazarus.py..."
if [ -f /home/solbot/fortress/fort_v2.py ]; then
  cp /home/solbot/fortress/fort_v2.py /home/solbot/fortress/lazarus.py
  echo "       Created lazarus.py (kept fort_v2.py as backup)"
else
  echo "       WARNING: fort_v2.py not found, skipping"
fi

# ---------- step 3: rename database ----------
echo "[3/8] Renaming fortress.db → lazarus.db..."
if [ -f /home/solbot/fortress/logs/fortress.db ]; then
  cp /home/solbot/fortress/logs/fortress.db /home/solbot/fortress/logs/lazarus.db
  echo "       Created lazarus.db (kept fortress.db as backup)"
else
  echo "       WARNING: fortress.db not found, skipping"
fi

# ---------- step 4: rename log file ----------
echo "[4/8] Renaming fort_v2.log → lazarus.log..."
if [ -f /home/solbot/fortress/logs/fort_v2.log ]; then
  cp /home/solbot/fortress/logs/fort_v2.log /home/solbot/fortress/logs/lazarus.log
  echo "       Created lazarus.log (kept fort_v2.log as backup)"
else
  echo "       WARNING: fort_v2.log not found, skipping"
fi

# ---------- step 5: update internal references in lazarus.py ----------
echo "[5/8] Updating internal references in lazarus.py..."
if [ -f /home/solbot/fortress/lazarus.py ]; then
  # Update banner/version string
  sed -i 's/Sol-Fortress/Lazarus/g' /home/solbot/fortress/lazarus.py
  sed -i 's/sol-fortress/lazarus/g' /home/solbot/fortress/lazarus.py
  sed -i 's/Sol_Fortress/Lazarus/g' /home/solbot/fortress/lazarus.py

  # Update database path references
  sed -i 's|logs/fortress\.db|logs/lazarus.db|g' /home/solbot/fortress/lazarus.py

  # Update log file references
  sed -i 's|logs/fort_v2\.log|logs/lazarus.log|g' /home/solbot/fortress/lazarus.py
  sed -i 's|fort_v2\.log|lazarus.log|g' /home/solbot/fortress/lazarus.py

  echo "       References updated in lazarus.py"
else
  echo "       WARNING: lazarus.py not found, skipping"
fi

# ---------- step 6: update references in supporting files ----------
echo "[6/8] Updating references in learning_engine.py and self_regulation.py..."
for f in /home/solbot/fortress/learning_engine.py /home/solbot/fortress/self_regulation.py; do
  if [ -f "$f" ]; then
    sed -i 's|logs/fortress\.db|logs/lazarus.db|g' "$f"
    sed -i 's/Sol-Fortress/Lazarus/g' "$f"
    sed -i 's/sol-fortress/lazarus/g' "$f"
    sed -i 's|fort_v2\.log|lazarus.log|g' "$f"
    echo "       Updated: $f"
  fi
done

# ---------- step 7: rename directory ----------
echo "[7/8] Renaming directory /home/solbot/fortress → /home/solbot/lazarus..."
mv /home/solbot/fortress /home/solbot/lazarus
echo "       Directory renamed."

# ---------- step 8: create new systemd services ----------
echo "[8/8] Creating new systemd services..."

# Lazarus bot service
cat > /etc/systemd/system/lazarus.service << 'UNIT'
[Unit]
Description=Lazarus Trading Engine (Moss Lane)
After=network.target

[Service]
Type=simple
User=solbot
WorkingDirectory=/home/solbot/lazarus
ExecStart=/home/solbot/lazarus/venv/bin/python /home/solbot/lazarus/lazarus.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

# Lazarus dashboard service
# First, find what the old dashboard service was running
OLD_DASH="/etc/systemd/system/sol-fortress-dashboard.service"
if [ -f "$OLD_DASH" ]; then
  DASH_EXEC=$(grep "ExecStart" "$OLD_DASH" | head -1 | sed 's/ExecStart=//')
  # Update the path from fortress to lazarus
  NEW_DASH_EXEC=$(echo "$DASH_EXEC" | sed 's|/fortress/|/lazarus/|g')
else
  NEW_DASH_EXEC="/home/solbot/lazarus/venv/bin/python /home/solbot/lazarus/dashboard.py"
fi

cat > /etc/systemd/system/lazarus-dashboard.service << UNIT2
[Unit]
Description=Lazarus Dashboard (Moss Lane)
After=network.target

[Service]
Type=simple
User=solbot
WorkingDirectory=/home/solbot/lazarus
ExecStart=${NEW_DASH_EXEC}
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT2

# Disable old services, enable new ones
systemctl disable sol-fortress-v2 2>/dev/null || true
systemctl disable sol-fortress-dashboard 2>/dev/null || true
systemctl daemon-reload
systemctl enable lazarus
systemctl enable lazarus-dashboard

echo "       New services created and enabled."

# ---------- verify ----------
echo ""
echo "========================================="
echo "  REBRAND COMPLETE"
echo "========================================="
echo ""
echo "  Directory:  /home/solbot/lazarus"
echo "  Bot file:   /home/solbot/lazarus/lazarus.py"
echo "  Database:   /home/solbot/lazarus/logs/lazarus.db"
echo "  Log:        /home/solbot/lazarus/logs/lazarus.log"
echo "  Bot svc:    lazarus"
echo "  Dash svc:   lazarus-dashboard"
echo ""
echo "  Old files kept as backups (fort_v2.py, fortress.db, fort_v2.log)"
echo ""

# Verify python syntax before starting
echo "Verifying Python syntax..."
if /home/solbot/lazarus/venv/bin/python -c "import py_compile; py_compile.compile('/home/solbot/lazarus/lazarus.py', doraise=True)" 2>/dev/null; then
  echo "  Syntax OK!"
  echo ""
  echo "Starting Lazarus..."
  systemctl start lazarus
  systemctl start lazarus-dashboard
  sleep 3
  systemctl status lazarus --no-pager -l | head -20
  echo ""
  echo "  Lazarus is LIVE. Welcome to Moss Lane."
else
  echo ""
  echo "  SYNTAX ERROR in lazarus.py — NOT starting service."
  echo "  Run: /home/solbot/lazarus/venv/bin/python -c \"import py_compile; py_compile.compile('/home/solbot/lazarus/lazarus.py', doraise=True)\""
  echo "  Fix the issue, then: systemctl start lazarus"
fi
