# Moss Lane — Thursday Sprint Plan (2026-04-09)
## Cloud SQL Wiring + Monitoring Foundation

**Prerequisite:** Wednesday 4/8 sprint complete. /health endpoint built, env hardened, deploy pipeline documented.

---

## Block 1 (9:00–10:00 AM) — Cloud SQL Provisioning

**Lead:** Lead Data Engineer (#3) | **Supporting:** SRE (#1)

**Objective:** Provision Cloud SQL for PostgreSQL, create the lazarus database, and connect it to Cloud Run.

### Tasks
- Provision Cloud SQL instance (PostgreSQL 15, us-east1, db-f1-micro for portfolio demo)
- Create `lazarus` database and `lazarus` user with scoped permissions
- Set the `DATABASE_URL` secret value in Secret Manager (connection string with Cloud SQL Auth Proxy socket path)
- Bind `DATABASE_URL` secret to Cloud Run service
- Set `DB_BACKEND=postgres` env var on Cloud Run
- Run schema migration — either `migrate_sqlite_to_pg.py` or let db_adapter.py auto-create tables on first boot
- Deploy new image (with updated entrypoint.sh from Wednesday)
- Verify /health returns `"backend": "postgres"` and `"status": "healthy"`

### Constraints
- [NO PLAINTEXT]: DATABASE_URL goes through Secret Manager only
- [FAIL-CLOSED]: If Cloud SQL is unreachable, /health returns 503
- [COST CONTROL]: db-f1-micro instance (~$7/mo), can be stopped when not demoing

### Blockers to Watch
- Cloud SQL Auth Proxy: Cloud Run uses a built-in connector (`/cloudsql/INSTANCE_CONNECTION_NAME`), not a sidecar. The DATABASE_URL format must use the Unix socket path, not TCP.
- db_adapter.py currently uses `psycopg2.connect(DATABASE_URL)` — verify this works with the Cloud SQL socket path format.
- Learning engine import path (`No module named 'learning_engine'`, TD-008) — non-blocking but will produce log noise.

### Exit Criteria
- /health endpoint returns healthy with postgres backend
- `SELECT COUNT(*) FROM trades` succeeds via Cloud SQL
- No plaintext DATABASE_URL in logs or `gcloud run services describe` output

---

## Block 2 (10:00–11:00 AM) — Monitoring Foundation

**Lead:** SRE / Risk Architect (#1) | **Supporting:** Observability Persona (#7)

**Objective:** Set up Cloud Run log-based metrics and alerting so failures are visible.

### Tasks
- Configure Cloud Logging sink for Lazarus container logs
- Create log-based metrics for key events:
  - `lazarus_scan_cycle` — count of main loop iterations (proves bot is alive)
  - `lazarus_trade_executed` — count of trade entries (paper or live)
  - `lazarus_error` — count of `ERROR` level log lines
  - `lazarus_health_unhealthy` — count of 503 responses from /health
- Create alert policies:
  - **P1:** No scan cycles logged in 10 minutes → alert (bot crashed or frozen)
  - **P1:** /health returning 503 for 5+ minutes → alert (DB or process down)
  - **P2:** Error rate > 10 per hour → alert (something degrading)
- Set up notification channel (email to josh)

### Constraints
- [DESIGNED vs BUILT]: Only mark metrics as Built once they're verified in Cloud Monitoring console
- [COST CONTROL]: Log-based metrics are free. Alert policies have a free tier of 6 per project.

### Exit Criteria
- At least 2 log-based metrics visible in Cloud Monitoring
- At least 1 alert policy configured and verified with a test trigger
- Alerting notification channel confirmed working

---

## Block 3 (11:00 AM–12:00 PM) — Integration Test + Image Deploy

**Lead:** QA Validation Architect (#5) | **Supporting:** Lead Data Engineer (#3)

**Objective:** Build and deploy a new Docker image with all Wednesday + Thursday changes. Run end-to-end verification.

### Tasks
- Build new Docker image with all changes (health endpoint, entrypoint.sh bridge, etc.)
- Push to Artifact Registry with new tag (e.g., v3.1.1 or v3.2)
- Deploy to Cloud Run
- End-to-end verification:
  - /health returns 200 with postgres backend, correct version, valid uptime
  - Bot logs show PAPER mode (not LIVE)
  - Bot logs show scan cycles running
  - No plaintext secrets in logs
  - Cloud Monitoring shows log-based metrics populating
- Scale to min-instances=0 after verification

### Constraints
- [WHITEBOARD TEST]: Must be able to explain the full flow from `docker build` to verified revision
- [NO LIVE TRADES]: Bot must be in PAPER mode on Cloud Run

### Exit Criteria
- New revision serving on Cloud Run
- /health green with postgres
- Monitoring metrics populating
- Bot in PAPER mode confirmed

---

## Block 4 (1:00–2:00 PM) — Documentation + Sprint Retro

**Lead:** TPM Meta-Persona (#4)

**Objective:** Update all tracking docs, close out the sprint, prepare for Friday.

### Tasks
- Update project ledger with Thursday results
- Update DEPLOY_PIPELINE.md Current State table (mark Cloud SQL as Built)
- Update go-live tracker if Stoic Gate has progressed on VPS
- Sprint retrospective: what went well, what didn't, what to carry forward
- Friday sprint plan (if applicable)

---

## Wednesday Blockers Carried Forward

These issues were surfaced during Wednesday's 4 blocks and need attention Thursday:

| ID | Blocker | Impact | Owner | Status |
|---|---|---|---|---|
| TD-007 | PAPER_TRADING not bridged to .env | Bot starts in LIVE mode on CR | entrypoint.sh | **Fixed** (Block 3 Wed) |
| TD-008 | Learning engine import path broken in Docker | `No module named 'learning_engine'` in logs | lazarus.py imports | Open — non-critical |
| B-001 | Cloud Run liveness probe not yet configured | Dockerfile HEALTHCHECK doesn't apply to CR | gcloud command needed | Open — needs manual config |
| B-002 | HELIUS_API_KEY created but not bound to CR | whale_watcher can't authenticate | gcloud update needed | Open — bind during Thursday deploy |
| B-003 | DATABASE_URL secret created but empty | No Cloud SQL instance yet | Thursday Block 1 | Open |
| B-004 | Go-live decision date (4/7) has passed | Stoic Gate at 7/20, needs rescheduling | Josh decision | Open — VPS track, not CR |

---

## Success Criteria for Thursday

By end of day:
1. Cloud SQL provisioned, connected, and verified via /health
2. At least one Cloud Monitoring alert policy active
3. New image deployed with all Wednesday+Thursday changes
4. Zero plaintext secrets anywhere in the deployment
5. Pipeline whiteboard-defensible: Build → Push → Deploy → Health → Monitor
