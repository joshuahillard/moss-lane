# Lazarus Environment Variable Audit & Secret Manager Plan
**Date:** 2026-04-08 | **Sprint Block 3** | **Owner:** Josh Hillard

---

## 1. Complete Env Var Inventory

### Sensitive — Must Use Secret Manager

| Variable | Read By | Read Method | SM Status | Notes |
|---|---|---|---|---|
| `SOLANA_PRIVATE_KEY` | lazarus.py:232 | EnvLoader → .env bridge | **EXISTS** | Wallet private key. Fatal if missing. |
| `SOLANA_RPC_URL` | lazarus.py:122 | EnvLoader → .env bridge | **EXISTS** | Helius/custom RPC. Has public default. |
| `BIRDEYE_API_KEY` | lazarus.py:121 | EnvLoader → .env bridge | **EXISTS** | Token scanning API key. |
| `DATABASE_URL` | db_adapter.py:37 | `os.environ.get()` | **NEEDS CREATION** | PostgreSQL connection string for Cloud SQL. Contains password. |
| `HELIUS_API_KEY` | whale_watcher.py:817 | `os.environ.get()` | **NEEDS CREATION** | Helius RPC key for whale watching. |
| `TAX_VAULT_KEY` | lazarus.py:1214 | EnvLoader → .env bridge | **NEEDS CREATION** | Tax vault wallet private key. Dispatcher only. |
| `EXEC_WALLET_1_KEY` | lazarus.py:208 | EnvLoader → .env bridge | **DEFERRED** | Executor wallet keys. Not deployed. |
| `EXEC_WALLET_2_KEY` | lazarus.py:208 | EnvLoader → .env bridge | **DEFERRED** | |
| `EXEC_WALLET_3_KEY` | lazarus.py:208 | EnvLoader → .env bridge | **DEFERRED** | |
| `EXEC_WALLET_4_KEY` | lazarus.py:208 | EnvLoader → .env bridge | **DEFERRED** | |
| `EXEC_WALLET_5_KEY` | lazarus.py:208 | EnvLoader → .env bridge | **DEFERRED** | |

### Non-Sensitive — Plain Env Vars on Cloud Run

| Variable | Read By | Read Method | Default | Cloud Run Setting |
|---|---|---|---|---|
| `PAPER_TRADING` | lazarus.py:186 | EnvLoader → .env bridge | `false` | Set to `true` until go-live |
| `DISPATCHER_ENABLED` | lazarus.py:203 | EnvLoader → .env bridge | `false` | Keep `false` |
| `DB_BACKEND` | db_adapter.py:36 | `os.environ.get()` | `sqlite` | Set to `postgres` for Cloud SQL |
| `LAZARUS_DB_PATH` | db_adapter.py:38 | `os.environ.get()` | `/home/solbot/lazarus/logs/lazarus.db` | Unused when DB_BACKEND=postgres |
| `VERTEX_AI_ENABLED` | vertex_predict.py:77 | `os.environ.get()` | `false` | Keep `false` |
| `PORT` | health_server.py | `os.environ.get()` | `8080` | Set by Cloud Run automatically |

### How Each Var Reaches the Code

There are two paths:

1. **EnvLoader path:** Cloud Run env var → entrypoint.sh writes to .env file → EnvLoader reads .env → lazarus.py uses `ENV.get()`
2. **os.environ path:** Cloud Run env var → Python reads directly via `os.environ.get()`

Variables that use EnvLoader (path 1) MUST be bridged in entrypoint.sh. Variables that use os.environ.get (path 2) work automatically.

| Variable | Path | Bridge Required? |
|---|---|---|
| SOLANA_PRIVATE_KEY | EnvLoader | Yes — in entrypoint.sh |
| SOLANA_RPC_URL | EnvLoader | Yes — in entrypoint.sh |
| BIRDEYE_API_KEY | EnvLoader | Yes — in entrypoint.sh |
| HELIUS_API_KEY | EnvLoader (via whale_watcher, which uses os.environ.get) + entrypoint.sh bridge | Bridge added for safety |
| TAX_VAULT_KEY | EnvLoader | Yes — added to entrypoint.sh |
| EXEC_WALLET_*_KEY | EnvLoader | Yes — added to entrypoint.sh |
| PAPER_TRADING | EnvLoader | Yes — **added to entrypoint.sh (fixes TD-007)** |
| DISPATCHER_ENABLED | EnvLoader | Yes — added to entrypoint.sh |
| DATABASE_URL | os.environ.get | No bridge needed |
| DB_BACKEND | os.environ.get | No bridge needed |

---

## 2. Secret Manager Commands

### Existing Secrets (already created 4/1-4/2)

```powershell
# Verify existing secrets
gcloud secrets list --project=moss-lane --filter="name:(SOLANA_PRIVATE_KEY OR SOLANA_RPC_URL OR BIRDEYE_API_KEY)"
```

### New Secrets to Create

```powershell
# DATABASE_URL — PostgreSQL connection string for Cloud SQL
# Format: postgresql://lazarus:<PASSWORD>@/<DB_NAME>?host=/cloudsql/<INSTANCE_CONNECTION_NAME>
# The actual value will be set tomorrow when Cloud SQL is provisioned.
gcloud secrets create DATABASE_URL --project=moss-lane --replication-policy="automatic"
# Placeholder — replace with real connection string after Cloud SQL setup:
# echo -n "postgresql://lazarus:CHANGEME@/lazarus?host=/cloudsql/moss-lane:us-east1:lazarus-db" | gcloud secrets versions add DATABASE_URL --project=moss-lane --data-file=-

# HELIUS_API_KEY — Helius RPC for whale watcher
gcloud secrets create HELIUS_API_KEY --project=moss-lane --replication-policy="automatic"
echo -n "<YOUR_HELIUS_KEY>" | gcloud secrets versions add HELIUS_API_KEY --project=moss-lane --data-file=-

# TAX_VAULT_KEY — tax vault wallet private key (when dispatcher is enabled)
gcloud secrets create TAX_VAULT_KEY --project=moss-lane --replication-policy="automatic"
# echo -n "<BASE58_PRIVATE_KEY>" | gcloud secrets versions add TAX_VAULT_KEY --project=moss-lane --data-file=-
```

### Grant Cloud Run Access to New Secrets

```powershell
# Get the Cloud Run service account
# Default: <PROJECT_NUMBER>-compute@developer.gserviceaccount.com
gcloud run services describe lazarus --region=us-east1 --format="value(spec.template.spec.serviceAccountName)" --project=moss-lane

# Grant secretAccessor role for each new secret
gcloud secrets add-iam-policy-binding DATABASE_URL --project=moss-lane --member="serviceAccount:<SA_EMAIL>" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding HELIUS_API_KEY --project=moss-lane --member="serviceAccount:<SA_EMAIL>" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding TAX_VAULT_KEY --project=moss-lane --member="serviceAccount:<SA_EMAIL>" --role="roles/secretmanager.secretAccessor"
```

---

## 3. Cloud Run Service Update

### Bind Secrets + Set Plain Env Vars

```powershell
gcloud run services update lazarus --region=us-east1 --project=moss-lane `
  --update-secrets=DATABASE_URL=DATABASE_URL:latest `
  --update-secrets=HELIUS_API_KEY=HELIUS_API_KEY:latest `
  --update-env-vars=PAPER_TRADING=true,DB_BACKEND=postgres,DISPATCHER_ENABLED=false
```

Note: `SOLANA_PRIVATE_KEY`, `SOLANA_RPC_URL`, and `BIRDEYE_API_KEY` are already bound from the initial deploy.

### Verify Configuration (No Plaintext Secrets)

```powershell
# This shows env vars and secret references — secret VALUES are never displayed
gcloud run services describe lazarus --region=us-east1 --project=moss-lane --format=yaml | Select-String -Pattern "env|secret"
```

---

## 4. Entrypoint.sh Changes (This Sprint)

The .env bridge in entrypoint.sh was updated to cover all EnvLoader-dependent vars:

**Added:**
- `HELIUS_API_KEY` — safety bridge (whale_watcher reads via os.environ, but future modules may use EnvLoader)
- `TAX_VAULT_KEY` — required when dispatcher is enabled
- `EXEC_WALLET_1_KEY` through `EXEC_WALLET_5_KEY` — loop-based bridge for executor wallets
- `PAPER_TRADING` — **fixes TD-007** (bot defaulted to LIVE on Cloud Run because this wasn't bridged)
- `DISPATCHER_ENABLED` — ensures dispatcher flag reaches EnvLoader

---

## 5. Log Audit — Sensitive Data Exposure

| File | Line | What's Logged | Safe? |
|---|---|---|---|
| lazarus.py:223 | `Birdeye key : {CFG['birdeye_key'][:8]}...` | First 8 chars + length | Yes — truncated |
| lazarus.py:224 | `RPC : {CFG['rpc_url'][:50]}` | First 50 chars of URL | Yes — no password in RPC URL |
| lazarus.py:225 | `Mode : PAPER/LIVE` | Boolean flag | Yes — not sensitive |
| lazarus.py:241 | `Wallet : {WALLET}` | Public key (not private) | Yes — public by design |
| lazarus.py:214 | `Invalid EXEC_WALLET_{i}_KEY: {e}` | Exception message only | Yes — no key value |
| lazarus.py:1220 | `Invalid TAX_VAULT_KEY: {e}` | Exception message only | Yes — no key value |
| entrypoint.sh:42 | `Generated $ENV_PATH from environment variables` | Path only, no values | Yes |

**No plaintext secrets are logged anywhere in the codebase.**

---

## 6. Three-Place Config Alignment

The "3-place config" rule (from incident 2026-03-28) requires values to be consistent across:
1. **Code** — CFG dict defaults in lazarus.py
2. **Database** — bot_config table
3. **Environment** — .env / Secret Manager

| Config Key | Code Default | DB (bot_config) | Env Var | Aligned? |
|---|---|---|---|---|
| birdeye_key | `""` (empty) | N/A | BIRDEYE_API_KEY (SM) | Yes — env overrides code |
| rpc_url | `api.mainnet-beta.solana.com` | N/A | SOLANA_RPC_URL (SM) | Yes — env overrides code |
| paper_trading | `false` | N/A | PAPER_TRADING (env var) | **Fixed this sprint** |
| db_backend | `sqlite` | N/A | DB_BACKEND (env var) | Needs `postgres` for Cloud SQL |

---

## 7. Remaining Work for Block 4 (Tomorrow)

1. Provision Cloud SQL instance
2. Create `lazarus` database and user
3. Set `DATABASE_URL` secret value with real connection string
4. Set `DB_BACKEND=postgres` on Cloud Run
5. Run `migrate_sqlite_to_pg.py` to seed schema
6. Deploy new image with updated entrypoint.sh
7. Verify /health endpoint reports `"backend": "postgres"` and healthy

---

## 8. ADR-006 Update — TAX_VAULT_KEY is Forbidden on the Trading Server (2026-04-30)

**Build log:** [docs/build-log/2026-04-30-adr006-vault-split.md](build-log/2026-04-30-adr006-vault-split.md)
**ADR:** [deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md](../../deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md) (ADR-006)

**The earlier guidance in section 1 of this document is superseded for `TAX_VAULT_KEY` only.** Per ADR-006, the tax vault private key must NEVER be present on the trading server — neither in `.env`, nor in process memory, nor as a Cloud Run secret bound to the lazarus service.

This inverts the prior treatment of `TAX_VAULT_KEY` (section 1 still lists it as a Secret Manager item to provision; that row is **historically accurate as of 2026-04-08 but is now obsolete**). Future doc-cleanup slice will rewrite section 1; in the meantime, this section is authoritative for `TAX_VAULT_KEY`.

### New invariant (in code)

A startup assertion at [src/data/data_integrity.py::assert_vault_topology](../src/data/data_integrity.py) refuses to start the service if `TAX_VAULT_KEY` is loadable from the environment, OR if `TAX_VAULT_ADDRESS` is missing. The assertion is invoked from [src/engine/lazarus.py](../src/engine/lazarus.py) in the existing Layer-4 startup-assertion block.

A deploy-time guard at [entrypoint.sh:60-74](../entrypoint.sh) aborts the container if `TAX_VAULT_KEY` is in the Cloud Run-injected env, giving a faster crash loop and a cleaner shell-level error than the Python assertion alone.

### What goes on the server

| Variable | Status |
|---|---|
| `TAX_VAULT_ADDRESS` | **Required.** Public address of the tax vault. Bridged by entrypoint.sh; read by lazarus.py to construct `TaxVaultConfig`. Plain env var on Cloud Run (or non-sensitive secret) — not a private key. |
| `TAX_VAULT_KEY` | **FORBIDDEN.** Refusing-to-start invariant. If present, see rotation procedure in the build log. |

### What goes off the server (operator side)

The vault private key is generated on a clean operator machine via:

```bash
export MOSS_LANE_OPERATOR_MACHINE=true
python -m src.finance.vault_keygen
```

The script prints the keypair once to stdout and never persists it. The operator records the private key on offline encrypted storage (laptop encrypted disk + offline backup; or hardware wallet). The script's reverse guard refuses to run on any machine that smells like the trading server (burner keys present, `/home/solbot/lazarus/` exists, or the allow-list flag is missing).

### Rotation procedure for existing deployments

If this server currently has `TAX_VAULT_KEY` in its `.env` or as a Cloud Run secret, follow [build log section (e)](build-log/2026-04-30-adr006-vault-split.md) before restarting the service. Mandatory steps:

1. Generate a new vault keypair on a clean operator machine.
2. Drain the old vault to the new vault (if old vault has SOL).
3. Edit `/home/solbot/lazarus/.env`: update `TAX_VAULT_ADDRESS`, REMOVE the `TAX_VAULT_KEY` line entirely.
4. Unbind the Cloud Run secret: `gcloud run services update lazarus --remove-secrets=TAX_VAULT_KEY`.
5. Bind `TAX_VAULT_ADDRESS` as a plain env var or non-sensitive secret.
6. Restart the service. Assertion will pass; `[STARTUP] OK: ADR-006 vault topology` appears in logs.

### Defense layers (after this change)

1. **Code-review guard:** [tests/unit/test_vault_topology_guards.py::test_no_tax_vault_key_writes_in_src](../tests/unit/test_vault_topology_guards.py) AST-walks src/ at CI time and fails any function body that pairs a literal `TAX_VAULT_KEY` string with a disk-write call.
2. **Runtime startup assertion:** `assert_vault_topology` in `src/data/data_integrity.py` fails closed at every startup.
3. **Deploy guard:** `entrypoint.sh:60-74` aborts container start if the env var is injected.
4. **Operator-side reverse guard:** `vault_keygen.py` refuses to generate a vault key on a machine that holds burner keys or has the server filesystem layout.

Reintroduction of the vulnerability requires defeating all four. Section 1 of this document (the historical TAX_VAULT_KEY row) is superseded by this section.
