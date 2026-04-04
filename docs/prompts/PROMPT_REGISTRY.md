# Moss Lane Prompt Registry
**LLM prompt version tracking for Lazarus trading engine**
*Created: April 4, 2026*

---

## Active Prompts

| Prompt ID | Component | Version | Model | Last Updated | Notes |
|-----------|-----------|---------|-------|-------------|-------|
| `TRADE_EVAL_V1` | `src/engine/lazarus.py` | 1.0 | N/A (rule-based) | v3.0 | Entry/exit signal evaluation |
| `REGIME_V1` | `src/engine/self_regulation.py` | 1.0 | N/A (rule-based) | v3.0 | Regime switching & auto-pause |
| `LEARNING_V1` | `src/engine/learning_engine.py` | 1.0 | N/A (statistical) | v3.0 | Self-learning parameter adjustment |

## How to Update

When changing a decision-making prompt or heuristic:
1. Bump the version in the source file
2. Update this registry with the new version and date
3. Document the change rationale in the build log

## Retired Prompts

| Prompt ID | Component | Retired | Reason |
|-----------|-----------|---------|--------|
| *(none yet)* | | | |

---
*Modeled after Ceal Prompt Registry pattern*
