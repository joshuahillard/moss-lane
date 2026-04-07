# Transaction Identity and Auditability

## What This Page Is

This page explains how Moss Lane should identify and reconstruct meaningful transactions across trading, configuration, analysis, and deployment.

Unlike the LLM project, Moss Lane does not revolve around a single document-evaluation key. It revolves around several operational transaction types that need to remain attributable:

- signal discovery
- trade execution and closure
- config changes
- deployment actions
- strategic decision checkpoints

## Why Identity Is Hard Here

A trading project can look auditable while still being hard to reconstruct.

Weak identifiers create problems such as:

- profitable and unprofitable trades being mixed across epochs
- paper and live behavior being conflated
- dynamic config values being attributed to the wrong learning window
- built modules being discussed as if they were the source of observed results
- deployment changes being hard to map back to runtime behavior

Moss Lane already has enough complexity that filename-based or memory-based identity is not sufficient.

## Current Authoritative Identifiers

The project currently relies on several real identifiers that already exist in the repo or documentation:

- trade table row IDs
- `timestamp` values in ISO text format
- `token_address`
- `wallet`
- `paper` flag
- `filter_regime`
- deploy script names and backup timestamps
- dated build logs, reports, and ledger entries

These are useful, but they are distributed across layers rather than unified.

## Recommended Canonical Transaction Types

### Trade transaction

Recommended identity shape:

```text
mode:epoch:wallet:token_address:entry_timestamp:filter_regime
```

Why these fields:

- `mode` separates paper from live
- `epoch` separates pre-fix and post-fix evaluation realities
- `wallet` matters now and will matter more if dispatcher goes live
- `token_address` is the real market object
- `entry_timestamp` distinguishes repeated interactions with the same token
- `filter_regime` preserves strategic context

### Config-change transaction

Recommended identity shape:

```text
config_layer:key:old_value:new_value:timestamp:source
```

This is especially important for:

- `bot_config`
- `dynamic_config`
- mode toggles
- live-readiness filter changes

### Deployment transaction

Recommended identity shape:

```text
deploy_script:target_service:backup_id:timestamp
```

This lines up with the project's existing backup-first deployment pattern.

### Decision-gate transaction

Recommended identity shape:

```text
decision_date:operating_mode:active_regime:evidence_window
```

This is the right level for go/no-go and roadmap decisions that are not just code changes.

## Audit Trail Requirements

For Moss Lane, a good audit trail should let someone answer:

- what exact regime and mode produced this performance claim?
- which trades were included?
- what config values were active?
- what code or deploy event changed the behavior?
- was this capability actually deployed, or only present in the repo?

## Current Audit Strengths

The project already has several strong audit habits:

- dated build logs tied to specific incidents
- a project ledger with timeline, ADRs, debt, and incidents
- deployment scripts that create backups
- architecture docs that distinguish some active vs. planned areas
- database fields that preserve mode and regime context

## Current Audit Gaps

The workspace also shows meaningful gaps:

- no single canonical transaction key spans all operational layers
- local test evidence is environment-sensitive and not yet normalized
- regime-aware learning attribution is still incomplete as a documented control
- built-vs-deployed truth still depends heavily on careful reading of docs rather than one authority file

## Practical Audit Standard for Moss Lane

Any major project claim should be traceable to all of the following:

1. a code artifact or config artifact
2. a dated evidence source
3. the operating mode
4. the epoch or time window
5. whether the claim is `deployed`, `repo-built`, or `planned`

If one of those is missing, the claim may still be useful, but it is not audit-grade.

## What This Foundation Enables Next

Stronger identity and auditability would make the following easier:

- live-vs-paper divergence analysis
- dispatcher rollout accountability
- regime-specific learning analysis
- cleaner go-live memos
- future investor, interviewer, or stakeholder walkthroughs grounded in one chain of evidence
