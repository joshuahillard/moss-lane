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
# 1. Starts health_server.py on $PORT (/health returns JSON with DB + process status)
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
    # ── Sensitive (from Secret Manager) ──
    [ -n "$SOLANA_PRIVATE_KEY" ] && echo "SOLANA_PRIVATE_KEY=$SOLANA_PRIVATE_KEY" >> "$ENV_PATH"
    [ -n "$SOLANA_RPC_URL" ]     && echo "SOLANA_RPC_URL=$SOLANA_RPC_URL" >> "$ENV_PATH"
    [ -n "$BIRDEYE_API_KEY" ]    && echo "BIRDEYE_API_KEY=$BIRDEYE_API_KEY" >> "$ENV_PATH"
    [ -n "$HELIUS_API_KEY" ]     && echo "HELIUS_API_KEY=$HELIUS_API_KEY" >> "$ENV_PATH"
    # ADR-006: TAX_VAULT_KEY is forbidden on the trading server.
    # Vault private key lives off-server (operator-side, generated via
    # src/finance/vault_keygen.py). Only TAX_VAULT_ADDRESS is bridged here;
    # the startup assertion in src/data/data_integrity.py::assert_vault_topology
    # fails closed if TAX_VAULT_KEY is ever found in the env.
    # See deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md (ADR-006).
    [ -n "$TAX_VAULT_ADDRESS" ]  && echo "TAX_VAULT_ADDRESS=$TAX_VAULT_ADDRESS" >> "$ENV_PATH"
    # Executor wallet keys (dispatcher mode — optional)
    for i in 1 2 3 4 5; do
        key_var="EXEC_WALLET_${i}_KEY"
        eval key_val=\$$key_var
        [ -n "$key_val" ] && echo "${key_var}=${key_val}" >> "$ENV_PATH"
    done
    # ── Non-sensitive (plain env vars on Cloud Run) ──
    # PAPER_TRADING must be bridged — lazarus.py reads it via EnvLoader, not os.environ.
    # This fixes TD-007: bot started in LIVE mode on Cloud Run because the env var
    # wasn't written to .env and EnvLoader defaulted to false.
    [ -n "$PAPER_TRADING" ]      && echo "PAPER_TRADING=$PAPER_TRADING" >> "$ENV_PATH"
    [ -n "$DISPATCHER_ENABLED" ] && echo "DISPATCHER_ENABLED=$DISPATCHER_ENABLED" >> "$ENV_PATH"
    # ── Database backend (Cloud SQL PostgreSQL) ──
    # On Cloud Run with Cloud SQL, DATABASE_URL is built from the Unix socket path
    # provided by the Cloud SQL Auth Proxy sidecar. DB_BACKEND tells db_adapter.py
    # to use psycopg2 instead of sqlite3.
    [ -n "$DB_BACKEND" ]         && echo "DB_BACKEND=$DB_BACKEND" >> "$ENV_PATH"
    [ -n "$DATABASE_URL" ]       && echo "DATABASE_URL=$DATABASE_URL" >> "$ENV_PATH"
    echo "Generated $ENV_PATH from environment variables"
fi

# ── ADR-006 deploy guard ────────────────────────────────────────────────────
# Refuse to start the container if TAX_VAULT_KEY is present in the injected
# environment. The Python startup assertion in
# src/data/data_integrity.py::assert_vault_topology also catches this, but
# failing here gives a cleaner shell exit and a faster crash loop on
# misconfigured deploys (no Python traceback in the container logs).
# Remediation: unbind the secret from this Cloud Run service:
#   gcloud run services update lazarus --remove-secrets=TAX_VAULT_KEY
# See deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md (ADR-006).
if [ -n "$TAX_VAULT_KEY" ]; then
    echo "P0 ADR-006: TAX_VAULT_KEY is present in the environment but is" >&2
    echo "forbidden on the trading server. Refusing to start." >&2
    echo "Unbind the secret: gcloud run services update lazarus --remove-secrets=TAX_VAULT_KEY" >&2
    exit 1
fi

# Start health check server in the background
# WHY: Replaces the old bare "ok" responder with a proper /health endpoint
# that reports service version, uptime, DB connectivity, and process status.
# Cloud Run liveness probe targets /health — unhealthy = 503 = no traffic (fail-closed).
python -m src.health.health_server "$PORT" &

# Run the bot as the main process — if it exits, the container exits
exec python -m src.engine.lazarus
