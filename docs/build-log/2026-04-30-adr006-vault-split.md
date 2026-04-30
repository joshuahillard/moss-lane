# Build Log — ADR-006 Vault Key Split

**Date:** 2026-04-30
**Phase:** 3, Slice 3 (out-of-band fix)
**Author:** Josh Hillard (TPM #4)
**Personas:** SecOps #2 (lead), DevOps #6, SRE #1
**Predecessor:** [docs/build-log/2026-04-30-phase3-slice2-dispatcher.md](2026-04-30-phase3-slice2-dispatcher.md)
**Companion ADR:** [deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md](../../../deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md) (ADR-006)
**Status:** Repo-built. Deployment pending operator action (Cloud Run secret unbind).

---

## a) Context — why this slice exists

ADR-006 (drafted 2026-04-29) declared the tax vault private key forbidden on the trading server. Server compromise must not mean vault loss. But the live code at the time of the ADR draft did exactly the wrong thing:

- [github-repo/src/finance/wallet_generator.py::generate_wallets](../../../github-repo/src/finance/wallet_generator.py) generated a `TAX_VAULT` keypair alongside the burners.
- [github-repo/src/finance/wallet_generator.py::save_wallets_to_env](../../../github-repo/src/finance/wallet_generator.py) wrote `TAX_VAULT_KEY` to `/home/solbot/lazarus/.env` next to the burner keys.
- [github-repo/src/engine/lazarus.py:1227](../../../github-repo/src/engine/lazarus.py) read `TAX_VAULT_KEY` at startup and derived the vault address from it.
- [github-repo/entrypoint.sh:32](../../../github-repo/entrypoint.sh) bridged `TAX_VAULT_KEY` from Cloud Run secrets to the .env file at container start.
- [github-repo/docs/ENV_AUDIT_AND_SECRET_MANAGER.md:17](../../../github-repo/docs/ENV_AUDIT_AND_SECRET_MANAGER.md) listed `TAX_VAULT_KEY` as a Secret Manager item to provision.

End-to-end: the vault private key was on the trading server's filesystem, in process memory, and bound as a Cloud Run secret. ADR-006's structural guarantee ("the key is not on the machine, so no code on the machine can sign for it") was violated by every layer.

This slice closes that gap.

---

## b) Pre-flight audit results

| Check | Finding |
|---|---|
| (a) `wallet_generator` callers in src/ | **Zero.** The module is invoked only via its `__main__` block. Refactoring is internally contained. |
| (b) `EnvLoader` callers | **Three independent class definitions** at [src/finance/wallet_generator.py:67](../../../github-repo/src/finance/wallet_generator.py:67), [src/engine/lazarus.py:93](../../../github-repo/src/engine/lazarus.py:93), [src/engine/fort_v2_clean.py:82](../../../github-repo/src/engine/fort_v2_clean.py:82). No `from finance.wallet_generator import EnvLoader` calls anywhere. The lazarus.py and fort_v2_clean.py copies are independent classes, not callers. |
| (c) `TAX_VAULT_KEY` runtime readers | One: [src/engine/lazarus.py:1227](../../../github-repo/src/engine/lazarus.py:1227) (`_tv_key = ENV.get("TAX_VAULT_KEY", "")`). All other matches are docstrings/comments/error messages. |
| (d) `.env` paths | Canonical: `/home/solbot/lazarus/.env`. Predecessor `fort_v2_clean.py` uses `/home/solbot/fortress/.env` (separate system, out of scope). 3 deploy scripts in deploy/ reference `.env` (none currently write `TAX_VAULT_KEY`). |
| (e) `WalletSet.tax_vault` consumers | **Zero external.** WalletSet/WalletConfig only referenced inside wallet_generator.py itself. Safe to drop the field. |

**Findings that required scope decisions** (gated with the operator before any code change):

1. **lazarus.py:1216-1243 needs a justified patch**, not just the assertion call. Without it, the post-rotation skim path silently disables on a properly-configured server. Approved.
2. **entrypoint.sh:32 needs the bridge line removed**, plus a defense-in-depth deploy guard that aborts container start if `TAX_VAULT_KEY` is injected. Approved.
3. **EnvLoader duplication** across lazarus.py + fort_v2_clean.py — out of scope for this slice (CLAUDE.md rule 1 risk on lazarus.py); tracked in the memory follow-ups index.

---

## c) Files touched

| File | Change |
|---|---|
| **NEW** [src/utils/env_loader.py](../../../github-repo/src/utils/env_loader.py) | Extracted `EnvLoader` class verbatim from wallet_generator.py. Public API (load, write) preserved exactly. Type annotations added; no behavior change. |
| **NEW** [src/utils/topology.py](../../../github-repo/src/utils/topology.py) | Extracted `TopologyError` + `validate_no_keys_in_env` from route_trade.py so both data_integrity and dispatcher import from a single source of truth (Stage 5 gate decision: "clean now"). |
| **NEW** [src/finance/vault_keygen.py](../../../github-repo/src/finance/vault_keygen.py) | Operator-only entrypoint. Layered reverse guard reports all failures at once (allow-list + burner-key + server-path checks). Strict `"true"` flag; strict `"yes"` confirmation; `EOFError` → no confirmation. Prints copy-paste-friendly keypair to stdout exactly once. No `EnvLoader` import, no `open()`, no `.env` reads or writes, no Solana RPC imports, no `transfer_out` / `withdraw` / `send` / `drain` / `sweep` / `spend_*` functions. |
| [src/finance/wallet_generator.py](../../../github-repo/src/finance/wallet_generator.py) | EnvLoader extracted (dual-import). `WalletSet.tax_vault` field removed. `ALLOCATION_PERCENTAGES["TAX_VAULT"]` removed. `generate_wallets` no longer creates the vault. `save_wallets_to_env` calls new `_assert_no_vault_key_in_env_updates` helper, raising `ValueError` (case-insensitive) on `TAX_VAULT_KEY`. `load_wallets_from_env`, `verify_all_wallets`, `verify_env_wallets`, `log_wallet_summary` no longer reference the vault. |
| [src/dispatcher/route_trade.py](../../../github-repo/src/dispatcher/route_trade.py) | `TopologyError` and `validate_no_keys_in_env` moved to `src/utils/topology.py`; re-imported here so existing callers' `from route_trade import TopologyError` and `from route_trade import validate_no_keys_in_env` continue to resolve. `import os` removed (no longer used). |
| [src/data/data_integrity.py](../../../github-repo/src/data/data_integrity.py) | New `assert_vault_topology(env=None)` function at end of Layer 4 section. Reuses `validate_no_keys_in_env` with narrowed `forbidden_suffixes=["TAX_VAULT_KEY"]` so legitimate burner/main keys held by lazarus aren't flagged. Logs `_log.critical(...)` before raising. Two operator-facing message constants: `_VAULT_ADDRESS_MISSING_MSG` (when address missing) and `_VAULT_KEY_ROTATION_MSG` (when key present — full rotation procedure embedded). |
| [src/engine/lazarus.py](../../../github-repo/src/engine/lazarus.py) | **Justified patch** (beyond the "two-line invocation" budget — see [Justifications](#justifications) below): TaxVault init at lines 1223-1239 reads `TAX_VAULT_ADDRESS` directly instead of deriving from `TAX_VAULT_KEY`. New single-line import of `assert_vault_topology` at line 52. New try/except wrapped call at lines 1325-1336 inside `if _DI:`, after the existing assertion try/except, matching the existing `[STARTUP] FAIL: ...` log style (Stage 5 gate decision: "Option B"). |
| [entrypoint.sh](../../../github-repo/entrypoint.sh) | **Justified patch**: removed `TAX_VAULT_KEY` bridge line; added `TAX_VAULT_ADDRESS` bridge line. Added 6-line deploy guard at lines 60-74 that aborts container start with a P0 message if `TAX_VAULT_KEY` is present in the injected env (Stage 5 gate decision: "add guard"). |
| **NEW** tests/unit/test_env_loader.py | 15 contract-preservation tests (load/write behavior, quoted values, backup, merge). |
| **NEW** tests/unit/test_wallet_generator_split.py | 11 tests on the burners-only split + the case-insensitive vault-key guard. |
| **NEW** tests/unit/test_vault_keygen.py | 26 tests on reverse guard layers, keypair generation, confirmation strictness, main flow, structural guarantees (no EnvLoader/open/write/outbound-signing). |
| **NEW** tests/unit/test_vault_topology_guards.py | 6 CI-style guards — AST walk for TAX_VAULT_KEY+write co-occurrence; TaxVault module surface checks (no outbound methods, no signing-substring, no engine imports); wallet_generator vault absence; vault_keygen no-disk-write. |
| **NEW** tests/unit/test_assert_vault_topology.py | 9 behavior tests (passes happy path, ignores legitimate burner keys, fails on missing address, fails on key present with rotation procedure in message, mock-confirms `validate_no_keys_in_env` is called with narrowed suffix list). |
| **NEW** tests/unit/test_tax_vault_skim_path.py | 6 regression tests confirming `TaxVault.calculate_skim` works with TAX_VAULT_ADDRESS only, no TAX_VAULT_KEY needed; ledger writes unchanged. |

### Justifications

The slice's stated constraint was "ONE import line + ONE call site" in lazarus.py, with anything beyond requiring explicit justification here.

**lazarus.py TaxVault init patch (lines 1223-1239):** The existing block read `TAX_VAULT_KEY` and derived the address via `Keypair.from_base58_string()`. After ADR-006 removes the key from .env, the existing block would silently fall through to `_tax_vault = None` and log "TAX_VAULT_KEY not configured — tax vault disabled". The skim path would be dead on every properly-configured server. Patch reads `ENV.get("TAX_VAULT_ADDRESS", "").strip()` directly. ~6 lines net change. Regression test [test_tax_vault_skim_path.py::test_skim_works_without_vault_private_key](../../../github-repo/tests/unit/test_tax_vault_skim_path.py) cannot pass without this patch.

**lazarus.py assertion try/except (lines 1325-1336):** Stage 5 gate decision was "Option B" — match the existing `[STARTUP] FAIL: ...` log style for parity with `validate_startup_config`. A bare `assert_vault_topology()` call would have raised `TopologyError` and produced a Python traceback in the container logs, not a clean log entry.

**entrypoint.sh deploy guard (lines 60-74):** Stage 5 gate decision was "add guard". Even after the bridge line is removed, the Cloud Run service may still have `TAX_VAULT_KEY` bound as a secret (operator must unbind it — see follow-ups). The guard catches the case in shell before Python starts, giving a faster crash loop and cleaner container log output.

---

## d) Before / after invariants

| Invariant | Before this slice | After this slice |
|---|---|---|
| Server `.env` contains `TAX_VAULT_KEY` | Yes — written by [save_wallets_to_env](../../../github-repo/src/finance/wallet_generator.py) and bridged by [entrypoint.sh:32](../../../github-repo/entrypoint.sh) | No — generation removed; bridge removed; runtime assertion fails-closed if present |
| `wallet_generator.generate_wallets()` creates a vault keypair | Yes | No — burners only |
| Server compromise → vault drained | Yes (single failure mode) | No (vault private key not on the server; AST guard catches reintroduction; runtime assertion catches re-injection; entrypoint deploy guard catches Cloud Run secret leak) |
| `TaxVault.calculate_skim` requires `TAX_VAULT_KEY` in env | Implicitly — lazarus init derived address from key | No — reads `TAX_VAULT_ADDRESS` directly |
| Vault keypair generation possible on a clean operator machine | No — wallet_generator generated server-side | Yes — `python -m src.finance.vault_keygen` after setting `MOSS_LANE_OPERATOR_MACHINE=true` |
| Operator can run `vault_keygen` on the trading server by mistake | Possible | No — layered reverse guard refuses (allow-list flag + burner-key check + `/home/solbot/lazarus/` path check, all reported at once) |
| `EnvLoader` lives in three independent definitions | Yes (still partially true — see follow-ups) | wallet_generator's copy is now extracted to `src/utils/env_loader.py`; lazarus.py + fort_v2_clean.py copies remain (out of slice scope) |
| `validate_no_keys_in_env` lives only in dispatcher | Yes | Moved to `src/utils/topology.py`; both data_integrity and dispatcher import from one source |

---

## e) Rotation procedure for existing deployments

**This procedure is mandatory before any server with TAX_VAULT_KEY in its environment can start the post-slice service.** It is also embedded verbatim in the assertion error message at [src/data/data_integrity.py::_VAULT_KEY_ROTATION_MSG](../../../github-repo/src/data/data_integrity.py).

**(1)** On an offline operator machine:

```bash
export MOSS_LANE_OPERATOR_MACHINE=true
python -m src.finance.vault_keygen
```

Record the printed public address and private key on offline encrypted storage. The script will not write the key to disk and will refuse to continue without explicit `yes` confirmation.

**(2)** If the OLD vault has accumulated SOL, drain it from a clean operator machine:

```bash
solana transfer --from <old-vault-keypair-file> --keypair <old-vault-keypair-file> \
  <new-vault-public-address> ALL --allow-unfunded-recipient
```

If the old vault is empty, skip this step. If RPC is unreachable, retry until it succeeds — do not proceed with funds left in the old vault.

**(3)** On the trading server, edit `/home/solbot/lazarus/.env`:

- Update `TAX_VAULT_ADDRESS` to the new vault public address
- **REMOVE** the `TAX_VAULT_KEY` line entirely (do not blank it; remove the line)

**(4)** Unbind the secret from Cloud Run:

```bash
gcloud run services update lazarus --region=us-east1 --project=moss-lane \
  --remove-secrets=TAX_VAULT_KEY
```

Verify with:
```bash
gcloud run services describe lazarus --region=us-east1 --project=moss-lane \
  --format=yaml | grep -i tax_vault
```

Should return only references to `TAX_VAULT_ADDRESS` (or nothing if not yet bound).

**(5)** Bind `TAX_VAULT_ADDRESS` as a plain env var on Cloud Run (or a non-sensitive secret):

```bash
gcloud run services update lazarus --region=us-east1 --project=moss-lane \
  --update-env-vars=TAX_VAULT_ADDRESS=<new-vault-public-address>
```

**(6)** Restart the service. The startup assertion will pass. Log line:
```
[STARTUP] OK: ADR-006 vault topology
```

If any step is missed, the service will refuse to start with the rotation procedure in the log.

---

## f) Expected behavior on developer machines

**This section calls out behavior that may surprise developers pulling this change. It is not a bug.**

After pulling this slice, **any developer with `TAX_VAULT_KEY` in their local `.env` will see lazarus refuse to start.** The startup assertion in `assert_vault_topology` is intentional fail-closed behavior — having `TAX_VAULT_KEY` on a developer machine has the same security profile as having it on the trading server (laptop compromise → vault drain).

### Developer remediation

Pick one of the following based on what the developer is doing:

1. **Paper trading / non-skim development**: remove the `TAX_VAULT_KEY` line from local `.env`. Add a `TAX_VAULT_ADDRESS` line pointing at any valid base58 pubkey (a fake-but-well-formed address is fine for non-skim flows). The skim path remains code-callable but never executes a real transfer in PAPER mode.

2. **Local skim path testing**: generate a test vault on your local machine (treating your laptop as the "operator" machine):
   ```bash
   export MOSS_LANE_OPERATOR_MACHINE=true
   python -m src.finance.vault_keygen
   ```
   Copy the printed `TAX_VAULT_ADDRESS=...` line to your local `.env`. The private key the script prints is for a devnet/test vault; do NOT use it for mainnet.

3. **Just want lazarus to import for unrelated work**: the assertion only runs at startup inside `async def main()`. Tests that import individual modules (e.g., `from src.data import db_adapter`) are unaffected. If a test imports lazarus.py directly, gate it behind a `TAX_VAULT_ADDRESS` env fixture.

### Why we chose fail-closed over a "soft" warning

The same assertion runs in production. A "soft" warning on missing/forbidden config would mask the real misconfiguration on a deployed server. Better to surface it loudly during development than to discover it after a vault drain.

---

## g) Test results

**Pre-slice baseline:** 100 tests across 5 files (test_filter_regime_write.py, test_fund_splitter.py, test_health.py, test_route_trade.py, test_startup_overrides.py). All passing.

**Post-slice:** 173 tests across 11 files. All passing. Pre-slice tests still pass; +73 net.

| Test file | Tests | Coverage |
|---|---|---|
| test_env_loader.py | 15 | Contract preservation: load/write/quoted-values/backup/merge |
| test_wallet_generator_split.py | 11 | Burners-only split + ValueError guard (case-insensitive) |
| test_vault_keygen.py | 26 | Reverse guard, keypair gen, confirmation, main flow, structural guarantees |
| test_vault_topology_guards.py | 6 | AST guard for TAX_VAULT_KEY+write, TaxVault no-outbound, wallet_generator no-vault, vault_keygen no-disk-write |
| test_assert_vault_topology.py | 9 | Pass/fail paths + mock-confirms validate_no_keys_in_env delegation |
| test_tax_vault_skim_path.py | 6 | Regression: skim works without TAX_VAULT_KEY; ledger unchanged |

Run command:
```bash
cd github-repo && python -m pytest tests/unit/ --tb=short
```

Result: `173 passed, 9 warnings in 0.77s` (warnings are pre-existing `datetime.utcnow()` deprecation, unchanged by this slice).

---

## h) Follow-ups

These are out of scope for the current slice. Tracked in the project memory at [memory/project_phase3_adr006_followups.md](../../../../memory/project_phase3_adr006_followups.md). Listed here for completeness.

1. **EnvLoader dedupe (LOW priority).** lazarus.py and fort_v2_clean.py still each define their own `EnvLoader` class. Future cleanup: have them import from `src/utils/env_loader.py`. Discipline: CLAUDE.md rule 1 — patch lazarus.py with targeted changes (replace class definition + the single ENV instantiation line), not wholesale rewrite.

2. **Cloud Run secret unbind (MEDIUM, OPERATOR ACTION REQUIRED).** Even after this slice's entrypoint.sh changes, the Cloud Run service likely still has `TAX_VAULT_KEY` bound as a secret reference. Operator must run `gcloud run services update lazarus --remove-secrets=TAX_VAULT_KEY` (see step 4 of the rotation procedure above). Until this lands, the deploy guard at entrypoint.sh:60-74 will trip on every deploy — which is the correct fail-closed behavior, but is also an operational papercut until unbound.

3. **Deploy script regeneration (MEDIUM).** Three deploy scripts in deploy/ reference `.env` writes (none currently write `TAX_VAULT_KEY`, but future regenerations could). Per CLAUDE.md rule 10, deploy scripts are base64-embedded and self-contained — modifying them in-slice would violate the deploy-script discipline. Next regeneration must include a pre-service-start guard: grep the `.env` for `TAX_VAULT_KEY`; abort deploy with P0 message if found. This duplicates the entrypoint.sh guard for defense in depth.

4. **ENV_AUDIT_AND_SECRET_MANAGER.md row inversion.** Line 17 of that doc currently lists `TAX_VAULT_KEY` as a Secret Manager item to provision. The append-only-EOF discipline (per project memory) means I cannot edit that line in this slice. The EOF append documents the new invariant, but the table at the top is misleading until a future doc-cleanup slice rewrites it.

---

## i) Deployed-vs-repo-built status

**This slice is repo-built. It is not yet deployed.**

Repo-built means: code, tests, and docs are committed and tests pass. The new invariants are enforced in any process that runs the post-slice code.

Deployment requires:
- (a) Operator-side vault keypair generation and `.env` rotation per the procedure in section (e) above
- (b) Cloud Run secret unbind (follow-up #2)
- (c) Container redeploy (entrypoint.sh changes don't take effect until the new image is built and deployed)

Until (a)–(c) are complete, the running production server still has the pre-slice configuration. The slice's protections protect against future regression in the codebase; they do not retroactively secure a server that already has TAX_VAULT_KEY in its environment.

Reference: *Foundations/Trust Boundaries in the Moss Lane Pipeline.md* — Boundary 7 (Deployment Truth).

---

*Quiet streets, loud comebacks.*
