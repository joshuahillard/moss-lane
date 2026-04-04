# Moss Lane Master Prompt Architecture
**Human-facing reference: how the prompt system works and why**
*Owner: Josh Hillard | Created: April 4, 2026 | Version: 1.0*

---

## What This Document Is (And Isn't)

This is the **design document** for Moss Lane's prompt system. It explains the architecture, the rationale, and how to maintain it. It is NOT pasted into AI sessions — the runtime prompts live in `RUNTIME_PROMPTS.md`.

---

## Problem

The original prompt approach had three failure modes:

**Fragmented context.** Project state was spread across overlapping documents (PROJECT_INSTRUCTIONS, sprint prompts, persona docs, session handoffs). Each new session had to reconcile slightly different versions.

**Sequential posting waste.** Each message re-established context that should already be loaded. Sprint prompts ranged from 5KB to 20KB, most of it background the model already knew.

**Rule reteaching.** Critical rules (EnvLoader, curl_get, VersionedTransaction signing) weren't front-loaded. Every session rediscovered the same failure modes.

---

## Architecture: Three Runtime Pieces + Optional Snapshot

```
CORE CONTRACT (stable, ~300-400 tokens)
  Architecture facts and hard rules only.
  Changes: when the stack changes or a new rule is adopted.
  Does NOT contain: repo state, counts, owner bio, trade history.

TASK CARD (per task, ~150-250 tokens)
  Goal, scope, out-of-scope, inspect-first symbols, acceptance, verify.
  Uses path::symbol references (durable across refactors).
  Verification is targeted to the task, not full-suite.

MODE PACK (optional, ~60-120 tokens)
  Domain-specific rules. Activated by task type.
  Available: MODE: engine, MODE: deploy, MODE: data, MODE: ml, MODE: infra
```

**Optional: SNAPSHOT block** (~50-100 tokens)
Attach only when the task depends on current trade state, Stoic Gate progress, or other volatile runtime data.

**Token budget:**
- Typical coding task: Core (~350) + Task Card (~200) = **~550 tokens**
- Task with domain rules: Core (~350) + Task Card (~200) + Mode (~80) = **~630 tokens**
- Task needing runtime state: add Snapshot (~80) = **~710 tokens**

---

## Maintenance Rules

1. **Core Contract** updates require updating `RUNTIME_PROMPTS.md` and this doc.
2. **Mode Packs** can be added independently — just append to RUNTIME_PROMPTS.md.
3. **Task Cards** are ephemeral — they live in the session, not in any file.
4. When a rule is added to Core Contract, remove it from any sprint-specific prompt.
5. This document tracks the *design*. Runtime prompts track the *text*.

---
*Modeled after Ceal Master Prompt Architecture pattern*
