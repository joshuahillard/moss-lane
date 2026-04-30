# Task 4 — GCP Artifact Registry Setup

> NONE of these commands have been run. Read each section, understand it,
> then run the commands yourself. Ask me if anything is unclear.

---

## What Is Artifact Registry?

Artifact Registry is Google Cloud's container image storage — think of it as
a private Docker Hub that only you can push to and pull from. When we deploy
to Cloud Run later, Cloud Run pulls the Lazarus image from here.

**Cost:** Free tier includes 500MB of storage. The Lazarus image is ~250MB.
You're well within free tier. You'd need to push ~2 full images before
hitting the limit, and old images can be deleted.

---

## Prerequisites

### 1. Install the gcloud CLI (if not already installed)

Check if it's installed:
```bash
gcloud --version
```

If not installed, download from: https://cloud.google.com/sdk/docs/install
- On Windows, this is a standard installer
- After install, restart your terminal

### 2. Authenticate with Google Cloud

This logs you into your Google account from the CLI:
```bash
gcloud auth login
```

**What happens:** Opens a browser window. Sign in with the Google account you
want to use for GCP. The CLI stores a token locally — no passwords saved.

### 3. Create a GCP Project (if you don't have one)

Check your existing projects:
```bash
gcloud projects list
```

If you need a new project:
```bash
gcloud projects create moss-lane --name="Moss Lane"
```

Then set it as your active project:
```bash
gcloud config set project moss-lane
```

> **Why "moss-lane"?** Project IDs are globally unique across all of GCP.
> If `moss-lane` is taken, try `moss-lane-lazarus` or similar. The project
> ID is permanent — choose something clean.

### 4. Enable billing

Artifact Registry requires a billing account even for free-tier usage.
Go to: https://console.cloud.google.com/billing

Link your project to a billing account. The 500MB free tier means you
won't be charged unless you exceed it.

---

## Step 1: Enable the Artifact Registry API

Google Cloud APIs are disabled by default. You must enable each one you use:

```bash
gcloud services enable artifactregistry.googleapis.com
```

**What this does:** Flips a switch in your project that says "yes, I want to
use Artifact Registry." No resources are created. No cost.

**Expected output:**
```
Operation "operations/..." finished successfully.
```

---

## Step 2: Create the Docker Repository

```bash
gcloud artifacts repositories create lazarus \
    --repository-format=docker \
    --location=us-east1 \
    --description="Lazarus trading bot Docker images"
```

**Breaking this down:**
- `lazarus` — the repository name (clean, descriptive)
- `--repository-format=docker` — this stores Docker images (not Maven, npm, etc.)
- `--location=us-east1` — South Carolina, closest GCP region to both your
  Boston location and your NJ VPS. Minimizes latency when Cloud Run hits the
  same Solana RPC endpoints your VPS uses.
- `--description` — human-readable label, visible in the console

**Cost:** $0. The repository itself is free. You pay only for stored bytes
beyond 500MB (which we won't hit with one ~250MB image).

**Expected output:**
```
Create request issued for: [lazarus]
Waiting for operation [...] to complete...done.
Created repository [lazarus].
```

**To tear this down later if needed:**
```bash
gcloud artifacts repositories delete lazarus --location=us-east1
```

---

## Step 3: Configure Docker to Push to Artifact Registry

This tells Docker on your machine "when I push to us-east1-docker.pkg.dev,
authenticate with my Google Cloud credentials":

```bash
gcloud auth configure-docker us-east1-docker.pkg.dev
```

**What this does:** Adds an entry to your `~/.docker/config.json` that maps
the Artifact Registry hostname to the gcloud credential helper. After this,
`docker push` to that hostname works automatically.

**Expected output:**
```
Adding credentials for: us-east1-docker.pkg.dev
Docker configuration file updated.
```

> This is a one-time setup per machine. You won't need to run it again
> unless you switch Google accounts.

---

## Step 4: Tag the Local Image for Artifact Registry

Docker images need a "full address" to know where to push. The format is:

```
REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/IMAGE:TAG
```

For us:
```bash
docker tag lazarus:latest us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:latest
```

**Breaking down the address:**
```
us-east1-docker.pkg.dev    ← Artifact Registry hostname (region-specific)
moss-lane                  ← your GCP project ID
lazarus                    ← the repository we created in Step 2
lazarus:latest             ← image name and tag
```

> **Replace `moss-lane`** with your actual GCP project ID if it's different.

**No output on success.** Verify with:
```bash
docker images | grep us-east1
```

---

## Step 5: Push the Image

```bash
docker push us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:latest
```

**What happens:**
1. Docker reads the tag, sees it points to Artifact Registry
2. The gcloud credential helper (from Step 3) authenticates the push
3. Docker uploads each layer of the image
4. Artifact Registry stores the image

**Expected output:**
```
The push refers to repository [us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus]
abc123: Pushed
def456: Pushed
ghi789: Pushed
latest: digest: sha256:... size: 1234
```

**Estimated upload time:** 1-3 minutes depending on your connection (~250MB).

---

## Step 6: Verify the Image Is in Artifact Registry

```bash
gcloud artifacts docker images list us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus
```

**Expected output:**
```
IMAGE                                                          DIGEST         CREATE_TIME          UPDATE_TIME
us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus   sha256:abc123   2026-04-01T...   2026-04-01T...
```

You can also see it in the web console:
https://console.cloud.google.com/artifacts/docker/moss-lane/us-east1/lazarus

---

## Summary: Full Command Sequence

Run these in order after reading and understanding each one:

```bash
# 1. Enable the API (free, just flips a switch)
gcloud services enable artifactregistry.googleapis.com

# 2. Create the repository (free, us-east1 for low latency)
gcloud artifacts repositories create lazarus \
    --repository-format=docker \
    --location=us-east1 \
    --description="Lazarus trading bot Docker images"

# 3. Configure Docker auth (one-time setup)
gcloud auth configure-docker us-east1-docker.pkg.dev

# 4. Tag your local image with the full Artifact Registry address
docker tag lazarus:latest us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:latest

# 5. Push the image
docker push us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:latest

# 6. Verify it's there
gcloud artifacts docker images list us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus
```

---

## Cost Summary

| Resource | Cost |
|----------|------|
| Artifact Registry API | Free |
| Repository (container) | Free |
| Storage (first 500MB) | Free |
| Lazarus image (~250MB) | Within free tier |
| Network egress (Cloud Run pulling from same region) | Free (intra-region) |

**Total: $0/month** as long as you stay under 500MB stored.

---

## Teardown (if needed)

Delete the image:
```bash
gcloud artifacts docker images delete \
    us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:latest
```

Delete the entire repository:
```bash
gcloud artifacts repositories delete lazarus --location=us-east1
```

Both are instant and free up all storage.

---

## What's Next

Once the image is pushed to Artifact Registry, Task 5 (Cloud Run) will pull
it from there and run it as a service. Artifact Registry is the bridge
between "works on my machine" and "runs in the cloud."
