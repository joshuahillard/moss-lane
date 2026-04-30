# Task 3 — Local Docker Testing Walkthrough

> Do NOT run these commands blindly. Read each section, understand what it does,
> then run it. This is a learning exercise.

---

## Problem: Two Hardcoded Paths

Before we can build, there are two paths in `lazarus.py` that point to the VPS
filesystem, not the container filesystem:

```
Line  83: EnvLoader(path="/home/solbot/lazarus/.env")
Line 106: DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"
```

Inside the container, the working directory is `/app`, so the files live at:
- `/app/.env` (volume-mounted from host)
- `/app/logs/lazarus.db` (volume-mounted from host)

### The Fix: Environment Variable Overrides (zero code changes)

Both paths can be overridden by setting environment variables that the bot reads
**before** it hits the hardcoded defaults. Add these to `docker-compose.yml`:

```yaml
environment:
  - LAZARUS_ENV=docker
  - LAZARUS_ENV_PATH=/app/.env
  - LAZARUS_DB_PATH=/app/logs/lazarus.db
```

Then, in a future lazarus.py update, the code would read:

```python
ENV = EnvLoader(path=os.environ.get("LAZARUS_ENV_PATH", "/home/solbot/lazarus/.env"))
DB_PATH = os.environ.get("LAZARUS_DB_PATH", "/home/solbot/lazarus/logs/lazarus.db")
```

**BUT** — the constraint says "do NOT touch the running Lazarus engine."

### Alternative Fix: Symlinks in the Dockerfile

We can make the container filesystem look like the VPS filesystem, so lazarus.py
finds its files at the paths it expects — no code changes required:

Add these lines to the Dockerfile (before the `USER solbot` line):

```dockerfile
# Create the directory structure lazarus.py expects, then symlink to /app
RUN mkdir -p /home/solbot/lazarus/logs \
    && ln -s /app/.env /home/solbot/lazarus/.env \
    && ln -s /app/logs /home/solbot/lazarus/logs \
    && chown -R solbot:solbot /home/solbot/lazarus
```

This way:
- `EnvLoader("/home/solbot/lazarus/.env")` follows the symlink → reads `/app/.env`
- `DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"` follows the symlink → writes to `/app/logs/lazarus.db`
- The volume mounts in docker-compose.yml still work (they mount to `/app/`)
- **Zero changes to lazarus.py**

---

## Step 1: Verify Your Directory Structure

Before building, your `PY/` directory should look like this:

```
PY/
├── .dockerignore
├── .env                  ← your secrets file (NEVER committed to git)
├── docker-compose.yml
├── Dockerfile
├── lazarus.py
├── learning_engine.py
├── requirements.txt
└── logs/                 ← create this empty directory
    └── (empty — lazarus.db will be created here on first run)
```

**Command to verify:**
```bash
ls -la PY/
```

**Create the logs directory if it doesn't exist:**
```bash
mkdir -p PY/logs
```

**Create a .env file for local testing** (use test values, NOT real keys):
```bash
cat > PY/.env << 'EOF'
SOLANA_PRIVATE_KEY=your_base58_private_key_here
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
BIRDEYE_API_KEY=your_birdeye_key_here
EOF
```

> IMPORTANT: If you want to test with real keys, use your actual .env file.
> If you just want to verify the container BUILDS and STARTS, test values
> are fine — the bot will fail on the first RPC call but the startup banner
> will still print.

---

## Step 2: Build the Docker Image

```bash
cd PY/
docker build -t lazarus:latest .
```

**What this does:**
1. Reads the Dockerfile
2. Pulls `python:3.12-slim` base image (first time only, ~150MB)
3. Runs `apt-get install curl` (the curl binary for `curl_get()`)
4. Creates the `solbot` user (non-root)
5. Copies `requirements.txt` and runs `pip install` (layer cached)
6. Copies `lazarus.py` and `learning_engine.py`
7. Creates symlinks so VPS paths resolve inside the container
8. Tags the final image as `lazarus:latest`

**Expected output (key lines to watch for):**
```
Step X/Y : RUN apt-get update && apt-get install -y --no-install-recommends curl
 ---> Running in abc123...
 ---> def456

Step X/Y : RUN pip install --no-cache-dir -r requirements.txt
Successfully installed aiohttp-3.x.x base58-2.x.x solders-0.x.x ...

Step X/Y : COPY lazarus.py .
 ---> ghi789

Successfully built <image-hash>
Successfully tagged lazarus:latest
```

**If the build fails:**
- `apt-get install curl` fails → you're probably behind a corporate proxy
- `pip install solders` fails → solders needs Rust; on ARM Macs, try `--platform linux/amd64`
- `COPY lazarus.py .` fails → make sure you're running from the PY/ directory

**Verify the image was created:**
```bash
docker images lazarus
```

Should show something like:
```
REPOSITORY   TAG       IMAGE ID       CREATED          SIZE
lazarus      latest    abc123def456   10 seconds ago   ~250MB
```

---

## Step 3: Run the Container

```bash
docker compose up -d
```

**What this does:**
1. Builds the image (if not already built)
2. Creates a container named `lazarus-bot`
3. Mounts `./.env` → `/app/.env` (read-only)
4. Mounts `./logs/` → `/app/logs/` (read-write)
5. Sets `LAZARUS_ENV=docker`
6. Starts `python lazarus.py` as user `solbot`
7. Applies memory limit (512MB) and CPU limit (0.5 cores)
8. Detaches (`-d`) so you get your terminal back

**Verify the container is running:**
```bash
docker ps
```

Expected output:
```
CONTAINER ID   IMAGE            STATUS                    NAMES
abc123         lazarus:latest   Up 5 seconds (healthy)    lazarus-bot
```

The `(healthy)` status comes from the HEALTHCHECK in the Dockerfile. It takes
~10 seconds (the start-period) before the first health check runs.

---

## Step 4: Check the Logs (The Real Test)

This is the moment of truth. If the startup banner prints, the bot initialized
successfully inside the container.

```bash
docker compose logs -f lazarus
```

**What you WANT to see (startup banner):**
```
INFO  ══════════════════════════════════════════════════════════════
INFO  Lazarus v3.0 — Solana Momentum Scalper
INFO  Mode: PAPER TRADING
INFO  Filters: chg 10.0-80.0%  mc $10K-$10M  liq >$50K  age >60m
INFO  ══════════════════════════════════════════════════════════════
INFO  Balance: X.XXX SOL ($XX.XX)
INFO  Scan cycle 1 starting...
```

**What you DON'T want to see:**
```
# Path error — means symlinks aren't working:
ERROR EnvLoader: [Errno 2] No such file or directory: '/home/solbot/lazarus/.env'

# Missing secret — means .env isn't mounted or is empty:
FATAL: SOLANA_PRIVATE_KEY missing from .env

# Missing curl — means apt-get install failed:
FileNotFoundError: [Errno 2] No such file or directory: 'curl'

# Import error — means pip install missed a dependency:
ModuleNotFoundError: No module named 'solders'
```

**Press Ctrl+C to stop following logs** (the container keeps running).

---

## Step 5: Verify Persistence

Check that the database was created on the HOST (not trapped in the container):

```bash
ls -la PY/logs/
```

You should see:
```
lazarus.db    ← created by the bot on first run
```

This file lives on your machine, not inside the container. If you run
`docker compose down` and then `docker compose up -d`, the database
survives — all trade history is preserved.

---

## Step 6: Verify curl Works Inside the Container

Open a shell inside the running container:

```bash
docker exec -it lazarus-bot bash
```

Then test curl:
```bash
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | head -c 200
```

You should see JSON output from DexScreener. This confirms `curl_get()` will
work inside the container.

Type `exit` to leave the container shell.

---

## Step 7: Stop and Clean Up

**Stop the container (keeps the image):**
```bash
docker compose down
```

**Remove the image too (full cleanup):**
```bash
docker compose down --rmi local
```

**Nuclear option (remove everything):**
```bash
docker compose down --rmi local -v
```
The `-v` flag removes the named volumes too. Your `./logs/` directory on the
host is a bind mount, NOT a named volume, so it survives even this.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Build | `docker build -t lazarus:latest .` |
| Start | `docker compose up -d` |
| Logs (follow) | `docker compose logs -f lazarus` |
| Status | `docker ps` |
| Shell into container | `docker exec -it lazarus-bot bash` |
| Stop | `docker compose down` |
| Rebuild after code change | `docker compose up -d --build` |
