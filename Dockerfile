# ══════════════════════════════════════════════════════════════════════════════
# Lazarus Trading Bot — Production Container
#
# WHY each decision:
#   python:3.12-slim  — matches VPS runtime exactly, minimal attack surface
#   curl installed    — curl_get() uses subprocess curl for all external HTTP
#   non-root user     — principle of least privilege (bot never needs root)
#   requirements first — Docker layer caching: deps rebuild only when they change
#   no .env in image  — secrets injected at runtime via env vars or volume mount
# ══════════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim

# ── System deps ──────────────────────────────────────────────────────────────
# curl is REQUIRED — lazarus.py curl_get() calls the curl binary via subprocess
# --no-install-recommends keeps the image lean (~5MB vs ~25MB)
# rm -rf /var/lib/apt/lists/* clears the apt cache (smaller final image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ────────────────────────────────────────────────────────────
# The bot never needs root. Running as root in a container is a security smell.
# Create user + group, then create the logs directory it will write to.
RUN groupadd --system solbot \
    && useradd --system --gid solbot --create-home solbot \
    && mkdir -p /app/logs \
    && chown -R solbot:solbot /app

WORKDIR /app

# ── Python deps (layer caching) ─────────────────────────────────────────────
# COPY requirements.txt FIRST, then install. This way, Docker caches the pip
# install layer. When you change lazarus.py but NOT requirements.txt, Docker
# skips the pip step entirely — rebuilds go from ~45s to ~3s.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
# These are the files that make up the Lazarus engine.
# .dockerignore prevents .env, logs/, __pycache__/ from leaking into the image.
COPY src/ ./src/
COPY entrypoint.sh .

# ── Path compatibility (zero code changes to lazarus.py) ────────────────────
# lazarus.py has two hardcoded VPS paths:
#   Line  83: EnvLoader(path="/home/solbot/lazarus/.env")
#   Line 106: DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"
#
# Instead of modifying the bot code, we create symlinks so the VPS paths
# resolve to the container's /app directory. The volume mounts in
# docker-compose.yml put the actual files at /app/.env and /app/logs/.
RUN mkdir -p /home/solbot/lazarus \
    && ln -s /app/.env /home/solbot/lazarus/.env \
    && ln -s /app/logs /home/solbot/lazarus/logs \
    && chown -R solbot:solbot /home/solbot/lazarus

# ── Switch to non-root ───────────────────────────────────────────────────────
USER solbot

# ── Health check ─────────────────────────────────────────────────────────────
# Every 30s, check if the python process is alive. If it's not, Docker marks
# the container "unhealthy" and the restart policy kicks in.
# Why pgrep? The bot has no HTTP endpoint — it's a background worker.
# --interval: how often to check
# --timeout: max time for the check command itself
# --retries: how many consecutive failures before "unhealthy"
# --start-period: grace period on startup (let the bot initialize)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD pgrep -f "python -m src.engine.lazarus" > /dev/null || exit 1

# ── Entry point ──────────────────────────────────────────────────────────────
# Cloud Run requires a container to listen on $PORT. Lazarus is a background
# worker, not a web service. entrypoint.sh starts a minimal health endpoint
# on $PORT alongside the bot so Cloud Run's startup probe passes.
# For local Docker (docker-compose), this also works — the health server
# just quietly runs in the background with no downside.
CMD ["bash", "entrypoint.sh"]
