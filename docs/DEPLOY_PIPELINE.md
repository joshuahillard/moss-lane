# Lazarus Cloud Run Deploy Pipeline
**Owner:** Josh Hillard | **Created:** 2026-04-08 | **Status:** Built and verified

---

## Pipeline Overview

Three stages. Windows dev machine → GCP Artifact Registry → Cloud Run.

```
┌─────────────────┐      ┌──────────────────────┐      ┌─────────────────────┐
│  1. BUILD       │      │  2. PUSH             │      │  3. DEPLOY          │
│                 │      │                      │      │                     │
│  Dockerfile     │─────▶│  Artifact Registry   │─────▶│  Cloud Run          │
│  docker build   │      │  us-east1            │      │  us-east1           │
│  local or Cloud │      │  docker.pkg.dev/     │      │  Secret Manager     │
│  Build          │      │  moss-lane/lazarus   │      │  Env vars           │
└─────────────────┘      └──────────────────────┘      └─────────────────────┘
```

---

## Stage 1: Build

**What:** Build a Docker image from the Dockerfile in github-repo/.

**Inputs:** Dockerfile, src/, entrypoint.sh, requirements.txt

**Self-healing steps in Dockerfile:**
- `sed -i 's/\r$//' entrypoint.sh` — strips CRLF from Windows Git (ADR-12)
- `chmod +x entrypoint.sh` — ensures executable bit survives cross-platform
- Symlinks `/home/solbot/lazarus/` → `/app/` so hardcoded VPS paths resolve in the container

**Command (local build):**
```powershell
cd C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo

docker build -t lazarus:v3.1 .
```

**Command (Cloud Build — alternative):**
```powershell
gcloud builds submit --tag us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1 --project=moss-lane
```

Cloud Build runs the Dockerfile remotely on GCP. No local Docker required. Both paths produce the same image.

**Verify:**
```powershell
docker images | Select-String lazarus
```

---

## Stage 2: Push to Artifact Registry

**What:** Tag and push the image to the Artifact Registry repository.

**Prerequisites (one-time, already done 4/1):**
- Artifact Registry API enabled
- Repository created: `us-east1-docker.pkg.dev/moss-lane/lazarus`
- Docker auth configured: `gcloud auth configure-docker us-east1-docker.pkg.dev`

**Commands (if built locally):**
```powershell
docker tag lazarus:v3.1 us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1

docker push us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1
```

If using `gcloud builds submit` in Stage 1, the image is already in Artifact Registry — skip this stage.

**Verify:**
```powershell
gcloud artifacts docker images list us-east1-docker.pkg.dev/moss-lane/lazarus --project=moss-lane
```

---

## Stage 3: Deploy to Cloud Run

**What:** Create or update the Cloud Run service from the Artifact Registry image.

**First deploy (already done 4/8):**
```powershell
gcloud run deploy lazarus `
  --image=us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1 `
  --region=us-east1 `
  --project=moss-lane `
  --platform=managed `
  --no-allow-unauthenticated `
  --min-instances=0 `
  --max-instances=1 `
  --memory=512Mi `
  --cpu=1 `
  --set-secrets=SOLANA_PRIVATE_KEY=SOLANA_PRIVATE_KEY:latest,SOLANA_RPC_URL=SOLANA_RPC_URL:latest,BIRDEYE_API_KEY=BIRDEYE_API_KEY:latest `
  --set-env-vars=PAPER_TRADING=true,DB_BACKEND=sqlite,DISPATCHER_ENABLED=false
```

**Subsequent deploys (image update only):**
```powershell
gcloud run services update lazarus `
  --image=us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1 `
  --region=us-east1 `
  --project=moss-lane
```

**Verify:**
```powershell
gcloud run revisions list --service=lazarus --region=us-east1 --project=moss-lane --limit=3

gcloud run services describe lazarus --region=us-east1 --project=moss-lane --format="value(status.url)"
```

---

## Secret Manager Integration

Secrets are injected as environment variables at container startup. The entrypoint.sh bridges EnvLoader-dependent vars to the .env file. Vars read via `os.environ.get()` work directly.

| Secret | SM Name | Bridge? | Status |
|---|---|---|---|
| SOLANA_PRIVATE_KEY | SOLANA_PRIVATE_KEY | Yes (entrypoint.sh) | Bound |
| SOLANA_RPC_URL | SOLANA_RPC_URL | Yes (entrypoint.sh) | Bound |
| BIRDEYE_API_KEY | BIRDEYE_API_KEY | Yes (entrypoint.sh) | Bound |
| HELIUS_API_KEY | HELIUS_API_KEY | Yes (entrypoint.sh) | Created, not yet bound |
| DATABASE_URL | DATABASE_URL | No (os.environ) | Not yet created |

See `docs/ENV_AUDIT_AND_SECRET_MANAGER.md` for the full inventory and binding commands.

---

## Health Check

The container runs health_server.py on $PORT alongside the trading engine.

| Endpoint | Response | Purpose |
|---|---|---|
| `GET /health` | JSON with DB + process status, 200 or 503 | Liveness probe target |
| `GET /` | `200 ok` | Backward compat |

**Dockerfile HEALTHCHECK** (local Docker only):
```
curl -sf http://localhost:${PORT:-8080}/health > /dev/null || exit 1
```

**Cloud Run** requires separate probe configuration (Cloud Run ignores Dockerfile HEALTHCHECK):
```powershell
gcloud run services update lazarus --region=us-east1 --project=moss-lane `
  --liveness-probe httpGet,path=/health,port=8080
```

---

## Rollback

Cloud Run retains previous revisions. To roll back:

```powershell
# List recent revisions
gcloud run revisions list --service=lazarus --region=us-east1 --project=moss-lane --limit=5

# Route traffic back to a previous revision
gcloud run services update-traffic lazarus `
  --region=us-east1 `
  --project=moss-lane `
  --to-revisions=lazarus-00013-2nf=100
```

---

## Current State (as of 2026-04-08)

| Component | Status | Evidence |
|---|---|---|
| GCP project (moss-lane) | Built | Created 4/1 |
| Artifact Registry repo | Built | us-east1-docker.pkg.dev/moss-lane/lazarus |
| Docker image v3.1 | Built | Pushed 4/8, verified in AR |
| Cloud Run service | Built | Revision lazarus-00013-2nf, us-east1 |
| Secret Manager (3 core) | Built | SOLANA_PRIVATE_KEY, SOLANA_RPC_URL, BIRDEYE_API_KEY |
| Secret Manager (HELIUS) | Built | Created 4/8, not yet bound to Cloud Run |
| Secret Manager (DATABASE_URL) | Designed | Needs Cloud SQL provisioning first |
| /health endpoint | Built | Returns JSON, fail-closed on DB/process failure |
| Liveness probe config | Designed | Cloud Run probe not yet pointed at /health |
| Cloud SQL instance | Designed | Thursday Block 1 |
| Monitoring / alerting | Designed | Thursday Block 2 |
| PAPER_TRADING bridge | Built | entrypoint.sh updated, fixes TD-007 |
| min-instances=0 | Built | Cost control for portfolio demo (ADR-13) |

---

## Deployment Checklist (Copy for Each Deploy)

```
[ ] Code changes committed and pushed to GitHub
[ ] Docker image built (local or Cloud Build)
[ ] Image pushed to Artifact Registry (if local build)
[ ] Image tag updated in gcloud run deploy command
[ ] Secret Manager bindings verified (no plaintext secrets)
[ ] Cloud Run deploy executed
[ ] New revision appears in revision list
[ ] /health endpoint returns 200 with correct version
[ ] Logs show bot started in correct mode (PAPER/LIVE)
[ ] No plaintext secrets visible in logs
[ ] Scale to min-instances=0 after verification (if portfolio demo)
```
