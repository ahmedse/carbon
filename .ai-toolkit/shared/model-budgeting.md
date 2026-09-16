# Model Budgeting — DeepSeek V4 Tiering, Cache, Off-Peak
# Read by: Master Architect, and any worker deciding which model to use.
# Source: curated from Carbon (2026-08) — provider-agnosticizable but tuned to DeepSeek V4.

> The single biggest cost lever is **not** picking a cheaper model — it's **cache
> hits** and **tier discipline**. A $0.003/M cache hit vs $0.15/M miss (Flash
> off-peak) is ~50x; peak hours are 2×.

---

## RULE 1 — One model per role (simplified)

| Role | Model |
|---|---|
| **All workers** — backend, frontend, devops, data-ml, debugger-fixer, qa-validator, product-designer, researcher, curator | **V4.1-Flash** (`deepseek-flash`) |
| **Master Architect** (only) | **V4-Pro** (`deepseek-v4-pro`) |
| Kimi, V3, R1 | **OFF roster** (cost / retired on provider) |

**Flash is far cheaper than Pro.** Tier by ROLE, not task complexity — workers never
escalate to Pro. Only the Master Architect reasons in V4-Pro.

---

## RULE 2 — Maximize cache hits (the biggest lever)

DeepSeek V4.1-Flash prefix-cache (off-peak): **hit ≈ $0.003/M vs miss ≈ $0.15/M (~50x).**
Peak (Mon–Fri 01:00–04:00 and 06:00–10:00 UTC) is **2×**.

- Keep a **STABLE, long-lived system prompt + tool definitions at the FRONT** of
  every LLM call. Never rotate them between calls.
- **Append** new context AFTER the stable prefix. Never reorder the prefix — a
  reorder invalidates the entire cache.
- Consequence: system prompts, role files, and tool schemas are versioned and
  append-only during a session; new instructions go at the end.

---

## RULE 3 — Off-peak + token discipline

- Run **batch/async generations off-peak** (half price). Example for Egypt
  (UTC+3, Cairo): peak = 04:00–07:00 and 09:00–13:00; off-peak = 13:00–04:00.
  Your timezone's peak varies — encode it once in `project.config.md`.
- **Cap output tokens**; prefer concise structured JSON.
- **Retrieve, don't stuff** — pull only the context the call needs instead of
  dumping the whole conversation.

---

## Cost table (per 1M tokens, USD — verify against current provider pricing)

| Model | cache-hit (off/peak) | cache-miss (off/peak) | output (off/peak) |
|---|---|---|---|
| V4.1-Flash | $0.003 / $0.006 | $0.15 / $0.30 | $0.60 / $1.20 |
| V4-Pro | $0.022 / $0.044 | $0.66 / $1.32 | $1.98 / $3.96 |

---

## Detection / audit (for verify.sh or review)

- Grep worker activation prompts for retired model names (`Kimi`, `Haiku`, `GPT-5`, `V3`, `R1`).
- Grep for "Pro" assigned to routine tasks (edits/tests/JSON) — a budgeting smell.
- Grep for system-prompt mutation mid-session (reordering the stable prefix).
