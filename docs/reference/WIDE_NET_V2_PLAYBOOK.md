# Wide-Net v2 Playbook
*April 7, 2026*

## Purpose

Define a narrower data-collection mode that preserves the profitable tight-mode momentum floor while collecting additional paper-mode samples above the current liquidity ceiling.

This is a research profile, not the default live trading posture.

## Why v2 Exists

Post-epoch paper results on April 7, 2026 showed:

- `original`: 10 trades, 50.0% WR, `+$443.82`, PF `2.18`
- `wide_net_v1`: 15 trades, 26.7% WR, `-$19.81`, PF `0.95`
- `wide_net_v1` with `chg_pct < 10` was decisively weak: 7 trades, 14.3% WR, `-$144.75`
- `30-80%` hourly change remained the strongest shared pocket across both cohorts

Conclusion: wide-net should not re-open sub-10% hourly movers. If we collect more data, it should happen by modestly widening the top of the range and the liquidity floor, not by lowering the momentum floor.

## Definition

`wide_net_v2` is the proposed paper-only research profile:

| Parameter | Tight Execution Mode | Wide-Net v1 | Wide-Net v2 |
|-----------|----------------------|-------------|-------------|
| `min_hourly_vol` | 400 | 400 | 400 |
| `min_chg_pct` | 10.0 | 5.0 | 10.0 |
| `max_chg_pct` | 80.0 | 120.0 | 100.0 |
| `min_liq` | 50,000 | 30,000 | 30,000 |
| `min_vmr` | 0.10 | 0.10 | 0.10 |
| `cooldown_seconds` | 7200 | 3600 | 7200 |

## Hypothesis

Wide-Net v2 should:

- preserve the proven `10%` momentum floor
- avoid the weakest `<10%` non-runner cohort
- collect additional data from `80-100%` movers
- collect additional data from the `30k-50k` liquidity band
- keep trade pacing and cooldown discipline closer to tight mode than wide-net v1

## Guardrails

- PAPER mode only
- JIT Final Gate unchanged
- fail-closed filter chain unchanged
- learning engine remains segmented from regime analysis
- all trade analysis must stay grouped by `filter_regime`
- do not treat `wide_net_v2` results as justification to relax tight mode without a post-epoch cohort comparison

## Cohort Tracking Note

Pre-v3.2 databases do not have a guaranteed `filter_regime` column. For `wide_net_v2` monitoring before the v3.2 migration lands, use inferred cohorts in SQL:

- `original_window`: `chg_pct >= 10 AND chg_pct < 80 AND liq >= 50000`
- `wide_net_v2_expansion`: `chg_pct >= 10 AND chg_pct < 100 AND liq >= 30000`, but not already in `original_window`

This preserves truthful cohort analysis before schema migration. After the v3.2 migration lands and runtime tagging is live, switch to the explicit `filter_regime` query pack for actual regime labels.

## VPS Deployment Note

On the current VPS, scanner thresholds are still emitted from the hardcoded `CFG` banner at startup. A DB-only mode switch was tested on April 7, 2026 and rolled back correctly because the service still started with `chg 10.0-80.0% | liq >$50,000`.

Use the code+DB deploy script for the actual v2 experiment:

- `deploy/lazarus_deploy_widenet_v2_code_db.sh`

## v3.2 Low-Volume Epoch

### Why v3.2 Exists

By April 15-16, 2026 the paper bot was no longer inside either documented envelope:

- service health was normal: `610` scan/candidate log lines in 6 hours, `0` entry lines
- DexScreener was healthy: `199-227` tokens seen per cycle
- filter starvation was persistent: `vol=118-123` plus `chg_low=62-66` were wiping out almost the entire 200-token scan set every cycle
- the 2-hour `vol` distribution clustered at `108-113` kills per cycle, confirming the problem was stable rather than a single flat pocket
- a live pump was visibly clipped: `stoat hit 284.0% h1` while `max_chg_pct=100.0` was active

Conclusion: keep the proven `10%` momentum floor, but relax the low-volume floor and the upper momentum ceiling long enough to test whether the scanner can re-enter the market without reopening the historically weak `<10%` cohort.

### v3.2 Profile

`v3.2_lowvol_epoch` is a paper-only mini-epoch with rollback ceremony:

| Parameter | Wide-Net v2 | v3.2 Low-Volume Epoch |
|-----------|-------------|-----------------------|
| `min_hourly_vol` | 400 | 250 |
| `min_chg_pct` | 10.0 | 10.0 |
| `max_chg_pct` | 100.0 | 120.0 |
| `min_liq` | 30,000 | 30,000 |
| `min_vmr` | 0.10 | 0.10 |
| `filter_regime` | inferred | `v3.2_lowvol_epoch` |

### Guardrails

- PAPER mode only
- 2-hour monitoring window after deploy
- non-zero candidate cycles are logged, but not required as an immediate hard gate
- automatic rollback if the 2-hour window shows zero non-zero candidate cycles and the filter breakdown shape is still effectively frozen
- trade rows must record `filter_regime` from runtime config, not from hardcoded branching logic
- the epoch marker must be written at patch-apply time as `epoch_v32_lowvol`

### Decision Logic

`v3.2` is not a replacement for `wide_net_v2`. It is an explicit out-of-envelope experiment for a quieter market state:

- keep `min_chg_pct=10.0` because the repo evidence already showed `<10%` was weak
- lower `min_hourly_vol` because the live scanner was dying on volume before any other filter had room to matter
- raise `max_chg_pct` to stop clipping legitimate runners like `stoat` at `284% h1`
- preserve the lower liquidity band from `wide_net_v2`

## Prompt / Model Change

When an AI session is explicitly running Wide-Net Data Collection Mode, default to the `wide_net_v2` profile unless Josh asks for a different experiment.

Use this language in task cards or runtime prompts:

```text
MODE: wide-net-data
PROFILE: wide_net_v2
GOAL: Collect paper-mode research data without reopening sub-10% hourly momentum entries.
```

Interpret `wide_net_v2` as:

- `min_hourly_vol = 400`
- `min_chg_pct = 10.0`
- `max_chg_pct = 100.0`
- `min_liq = 30000`
- `min_vmr = 0.10`
- `cooldown_seconds = 7200`

## Artifacts

- Deploy script (DB-only validator): `deploy/lazarus_deploy_widenet_v2.sh`
- Deploy script (actual VPS switch): `deploy/lazarus_deploy_widenet_v2_code_db.sh`
- Deploy script (v3.2 low-volume epoch): `deploy/lazarus_deploy_v32_lowvol_epoch.sh`
- Query pack (default, legacy-safe): `docs/reference/WIDE_NET_V2_QUERY_PACK.sql`
- Query pack (explicit legacy naming): `docs/reference/WIDE_NET_V2_QUERY_PACK_LEGACY.sql`
- Query pack (post-migration, uses `filter_regime`): `docs/reference/WIDE_NET_V2_QUERY_PACK_V32.sql`
