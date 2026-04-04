#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Cloud Run Entrypoint
#
# WHY THIS EXISTS:
# Cloud Run expects a container to listen on $PORT (default 8080). Lazarus is
# a background worker, not a web service. This script starts a minimal HTTP
# health endpoint alongside the bot so Cloud Run's health check passes.
#
# WHAT IT DOES:
# 1. Starts a one-line Python HTTP server on $PORT (responds 200 to any request)
# 2. Starts lazarus.py as the main process
# 3. If lazarus.py exits, the container exits (Cloud Run restarts it)
# ══════════════════════════════════════════════════════════════════════════════

PORT="${PORT:-8080}"
ENV_PATH="/home/solbot/lazarus/.env"

# ── Generate .env from Cloud Run secret env vars ────────────────────────────
# On Cloud Run, secrets are injected as environment variables (via Secret
# Manager), but lazarus.py's EnvLoader reads from a .env FILE. This bridge
# writes the env vars into the file EnvLoader expects.
# On local Docker, the .env is volume-mounted and already exists — skip.
if [ ! -f "$ENV_PATH" ]; then
    mkdir -p "$(dirname "$ENV_PATH")"
    : > "$ENV_PATH"
    [ -n "$SOLANA_PRIVATE_KEY" ] && echo "SOLANA_PRIVATE_KEY=$SOLANA_PRIVATE_KEY" >> "$ENV_PATH"
    [ -n "$SOLANA_RPC_URL" ]     && echo "SOLANA_RPC_URL=$SOLANA_RPC_URL" >> "$ENV_PATH"
    [ -n "$BIRDEYE_API_KEY" ]    && echo "BIRDEYE_API_KEY=$BIRDEYE_API_KEY" >> "$ENV_PATH"
    echo "Generated $ENV_PATH from environment variables"
fi

# Start a minimal health check server in the background
python -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, *args):
        pass  # suppress access logs

HTTPServer(('0.0.0.0', int(sys.argv[1])), Health).serve_forever()
" "$PORT" &

# Run the bot as the main process — if it exits, the container exits
exec python -m src.engine.lazarus
