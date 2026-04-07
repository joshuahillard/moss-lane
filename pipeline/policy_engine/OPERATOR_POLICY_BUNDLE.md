# Operator Policy Bundle

## What This Page Is

This document defines the operating policy bundle for Moss Lane at the documentation level. It is the policy equivalent of the control-plane rules: what the project values, what it rejects, what requires escalation, and what must be true before the next operating stage is authorized.

## Policy Priorities

1. Capital preservation outranks experimentation.
2. Data integrity outranks performance storytelling.
3. Runtime truth outranks portfolio polish.
4. Deployed behavior outranks repo ambition.
5. Human-governed stage transitions outrank autonomous optimism.

## Approve Policy

Approve a state, claim, or next-step recommendation only when:

- the claim matches current evidence
- the operating mode is explicit
- the regime context is explicit
- the control path is bounded
- the next action does not hide a known integrity gap

Examples:

- validating the exit-chain behavior from a real documented paper trade
- affirming that the 5-layer data integrity system materially improved trust
- using original-filter evidence to justify revisiting tight filters

## Reject Policy

Reject a state, claim, or plan when:

- it treats undeployed work as operational fact
- it relies on known-bad query or timestamp logic
- it writes adaptive config outside safe bounds
- it blurs paper and live evidence
- it declares go-live readiness without cleaning up regime or observability concerns

## Escalate Policy

Escalate rather than force a yes/no when:

- the code works but the strategic implication is still unclear
- the evidence window is mixed or incomplete
- the next move has hidden operational tradeoffs
- the project is deciding between profit-first and portfolio-first sequencing

Examples:

- VPS-first vs. GCP-first go-live path
- whether dispatcher should remain staged or be deployed
- whether the learning engine should be reset, segmented, or made regime-aware

## Truthfulness Policy

Every major subsystem should be labeled as one of:

- `deployed`
- `repo-built`
- `planned`

This should become a standing rule for future docs and status reports.

## Go-Live Policy

The project should not authorize go-live until the following questions are answered explicitly:

1. Which filter regime is the live regime?
2. Does the learning layer align with that regime?
3. Are paper/live accounting paths verified?
4. Is the rollback path clear?
5. Is observability sufficient for the first real-money phase?

If any answer remains unclear, the correct outcome is escalation, not approval.
