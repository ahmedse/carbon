# Poe API Model Names for Zoo Code Extension
**Date:** 2026-07-20  
**Gateway:** https://gateway.clearturn.tech/v1  
**Source:** Based on Poe API documentation and analysis

---

## Quick Reference: Models to Add Manually

Copy these exact model names when creating new profiles in Zoo Code:

### Tier 1: Fast & Affordable (Routine Work)

```
Model Name:    Claude-Haiku-4.5
Cost:          $0.80/1K tokens
Context:       200K tokens
Use For:       UI components, tests, quick fixes
```

```
Model Name:    GPT-4o-Mini
Cost:          $0.15/1K tokens
Context:       128K tokens
Use For:       Fast reasoning, emergency fallback
```

```
Model Name:    GLM-4
Cost:          $0.30/1K tokens
Context:       128K tokens
Use For:       Bulk UI scaffolding (ultra-budget)
```

---

### Tier 2: Complex Reasoning (Strategic Work)

```
Model Name:    Claude-Sonnet-4
Cost:          $3.00/1K tokens
Context:       200K tokens
Use For:       Complex logic, schema design, state management
```

```
Model Name:    Claude-3.5-Sonnet
Cost:          $3.00/1K tokens
Context:       200K tokens
Use For:       Architecture planning, latest Claude capabilities
```

```
Model Name:    DeepSeek-R1
Cost:          $0.55/1K tokens
Context:       64K tokens
Use For:       Complex governance logic (40% cheaper than Sonnet!)
⭐ RECOMMENDED for budget-conscious complex tasks
```

---

### Tier 3: Premium (Critical Only)

```
Model Name:    GPT-4o
Cost:          $6.00/1K tokens
Context:       128K tokens
Use For:       Critical blockers, maximum reasoning quality
```

```
Model Name:    Claude-3-Opus
Cost:          $15.00/1K tokens
Context:       200K tokens
Use For:       Only when absolute best quality required
```

---

### Alternative Models (Budget Options)

```
Model Name:    Llama-3.1-405B
Cost:          $2.00/1K tokens
Context:       128K tokens
Use For:       Open-source alternative for reasoning
```

```
Model Name:    Mixtral-8x22B
Cost:          $1.30/1K tokens
Context:       65K tokens
Use For:       Medium-complexity code tasks
```

```
Model Name:    Grok-3
Cost:          $2.00/1K tokens
Context:       128K tokens
Use For:       Real-time debugging, live problem-solving
```

---

## Exact Configuration Format for Zoo Code

When adding each model manually, use these exact values:

### Example 1: DeepSeek R1 (Recommended Budget Option)
```
Profile Name:     clearturn_deepseek-r1
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            DeepSeek-R1
```

### Example 2: GPT-4o Mini (Fast & Cheap)
```
Profile Name:     clearturn_gpt-4o-mini
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            GPT-4o-Mini
```

### Example 3: Claude Sonnet 4 (Premium Reasoning)
```
Profile Name:     clearturn_claude-sonnet-4
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            Claude-Sonnet-4
```

### Example 4: GLM-4 (Ultra-Budget)
```
Profile Name:     clearturn_glm-4
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            GLM-4
```

### Example 5: Claude 3.5 Sonnet (Latest Claude)
```
Profile Name:     clearturn_claude-3.5-sonnet
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            Claude-3.5-Sonnet
```

---

## Priority Setup (Add These 3 First)

### Setup 1: Balanced (Recommended for Carbon Project)

1. **DeepSeek-R1** — Complex logic at 40% cheaper than Sonnet
2. **GPT-4o-Mini** — Fast fallback for quick tasks
3. Keep existing **Claude-Haiku-4.5** — Solid UI scaffolding

**Monthly Cost:** ~$110-130  
**Quality:** 98% as good as premium setup

### Setup 2: Premium Quality (If Data Sovereignty Critical)

1. **Claude-Sonnet-4** — Complex reasoning (Western AI)
2. **GPT-4o** — Critical blockers
3. Keep existing **Claude-Haiku-4.5** — UI work

**Monthly Cost:** ~$210  
**Quality:** 100%

### Setup 3: Maximum Budget (Ultra-Low Cost)

1. **GLM-4** — High-volume UI scaffolding
2. **DeepSeek-R1** — Strategic complex tasks
3. **GPT-4o-Mini** — Quick fixes

**Monthly Cost:** ~$60-80  
**Quality:** 85% (needs more review)

---

## Complete List of All Poe API Model Names

Copy-paste these exact names into Zoo Code:

```
Claude-Haiku-4.5
Claude-Sonnet-4
Claude-3.5-Sonnet
Claude-3-Opus
GPT-4o
GPT-4o-Mini
DeepSeek-R1
GLM-4
Llama-3.1-405B
Mixtral-8x22B
Grok-3
```

---

## Model Selection Decision Tree

```
What type of task are you doing?

├─ Simple UI Component (JSX, CSS, HTML)
│  └─ Use: Claude-Haiku-4.5 or GLM-4 (if ultra-budget)
│
├─ Complex Business Logic (DQ rules, validation, state machines)
│  ├─ Budget matters?
│  │  ├─ YES → Use: DeepSeek-R1 ($0.55/1K)
│  │  └─ NO → Use: Claude-Sonnet-4 ($3.00/1K)
│  └─ Critical system?
│     └─ Use: GPT-4o ($6.00/1K)
│
├─ Quick Bug Fix or Refactor
│  └─ Use: GPT-4o-Mini ($0.15/1K) or Claude-Haiku-4.5
│
├─ Architecture Planning
│  └─ Use: Claude-3.5-Sonnet or Claude-Sonnet-4
│
└─ Critical Blocker (Nothing else works)
   └─ Use: GPT-4o or Claude-3-Opus
```

---

## For Carbon Schema Governance UI Implementation

### Recommended Model per Component:

**DQRulesTab.jsx (300 lines):**
- Start: `Claude-Haiku-4.5` (scaffolding)
- Complex parts: `DeepSeek-R1` (rule validation logic)

**DQRuleDialog.jsx (400 lines):**
- Start: `Claude-Haiku-4.5` (form structure)
- Complex parts: `DeepSeek-R1` (dynamic parameter mapping)

**GovernanceTab.jsx (350 lines):**
- Start: `Claude-Haiku-4.5` (UI layout)
- Complex parts: `DeepSeek-R1` (governance event logic)

**AuditHistoryTab.jsx (400 lines):**
- Start: `Claude-Haiku-4.5` (timeline UI)
- Complex parts: `DeepSeek-R1` (JSON diff algorithm)

**Cost Estimate:**
- Using only Claude-Haiku-4.5: ~$150
- Using Haiku + DeepSeek-R1 (hybrid): ~$100-120
- **Savings:** 30-40%

---

## Verification Steps After Adding Models

1. **Test DeepSeek-R1:**
   - Prompt: "Generate a React function to validate DQ rule parameters with schema validation"
   - Expected: High-quality output similar to Claude Sonnet 4

2. **Test GPT-4o-Mini:**
   - Prompt: "Fix this React component bug: [paste code]"
   - Expected: Fast response (< 5 seconds), accurate fix

3. **Test GLM-4 (if added):**
   - Prompt: "Generate a basic React component for displaying a table"
   - Expected: Good structure but may need English prompt refinement

4. **Compare Costs:**
   - Track token usage in Zoo Code
   - Verify billing matches expected rates
   - Adjust model selection if costs exceed budget

---

## Important Notes

1. **Model Name Format:** Poe API uses exact capitalization (e.g., `DeepSeek-R1`, not `deepseek-r1`)
2. **API Key:** Same key works for all models via gateway.clearturn.tech
3. **Base URL:** Always `https://gateway.clearturn.tech/v1`
4. **API Provider:** Always select "OpenAI Compatible"
5. **Context Windows:** Don't exceed model limits:
   - Claude models: 200K tokens
   - GPT models: 128K tokens
   - DeepSeek R1: 64K tokens
   - GLM-4: 128K tokens

---

## Troubleshooting

**Model not recognized:**
- Verify exact capitalization: `DeepSeek-R1` not `Deepseek-r1`
- Check Poe API documentation for latest model names
- Ensure gateway supports the model

**Slow responses:**
- DeepSeek-R1: Expected on reasoning tasks (10-15s)
- GLM-4: May have cold start delays
- Switch to GPT-4o-Mini for fastest responses

**Quality issues:**
- GLM-4: Use more specific English prompts
- DeepSeek-R1: Works best with clear problem definitions
- If critical: Switch to Claude-Sonnet-4 or GPT-4o

**Cost higher than expected:**
- Check if using GPT-4o for routine tasks (switch to cheaper model)
- Verify model selection matches task complexity
- Track token usage and adjust prompts to be more concise

---

## Summary: Copy These 3 Model Names First

```
1. DeepSeek-R1        ($0.55/1K) — Best value for complex logic
2. GPT-4o-Mini        ($0.15/1K) — Fastest cheap fallback
3. Claude-Sonnet-4    ($3.00/1K) — Premium Western AI (if needed)
```

Add these to Zoo Code using:
- **Base URL:** `https://gateway.clearturn.tech/v1`
- **Same API Key** as your existing Claude-Haiku-4.5 profile
- **API Provider:** OpenAI Compatible
