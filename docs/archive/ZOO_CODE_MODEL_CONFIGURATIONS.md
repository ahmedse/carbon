ct # Zoo Code Extension - Additional Model Configurations
**Date:** 2026-07-20  
**Gateway:** https://gateway.clearturn.tech/v1  
**Purpose:** Add DeepSeek R1, GLM-4, and other recommended models to Zoo Code extension

---

## Overview

Based on the AI models analysis ([`POE_MODELS_ANALYSIS_DEVELOPMENT_STRATEGY.md`](POE_MODELS_ANALYSIS_DEVELOPMENT_STRATEGY.md)), this guide provides configuration profiles for adding cost-effective models to Zoo Code extension using the existing ClearTurn gateway.

All models use the same:
- **Base URL:** `https://gateway.clearturn.tech/v1`
- **API Key:** (same as current `clearturn_claude-haiku-4.5` profile)
- **API Provider:** OpenAI Compatible

---

## Configuration Profiles to Add

### 1. Claude Haiku 4.5 (Current - Reference)
```
Profile Name:     clearturn_claude-haiku-4.5
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [your-existing-key]
Model:            anthropic/claude-haiku-4.5
Context Window:   200,000 tokens
Cost:             $0.80/1K tokens
```

### 2. Claude Sonnet 4 (Complex Reasoning)
```
Profile Name:     clearturn_claude-sonnet-4
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            anthropic/claude-sonnet-4
Context Window:   200,000 tokens
Cost:             $3.00/1K tokens
Use For:          Complex schema logic, DQ validation, state machines
```

### 3. Claude 3.5 Sonnet (Latest Premium)
```
Profile Name:     clearturn_claude-3.5-sonnet
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            anthropic/claude-3.5-sonnet
Context Window:   200,000 tokens
Cost:             $3.00/1K tokens
Use For:          Architecture reviews, multi-system integration
```

### 4. GPT-4o (Premium Reasoning)
```
Profile Name:     clearturn_gpt-4o
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            openai/gpt-4o
Context Window:   128,000 tokens
Cost:             $6.00/1K tokens
Use For:          Critical blockers, complex governance algorithms
```

### 5. GPT-4o Mini (Fast & Cheap)
```
Profile Name:     clearturn_gpt-4o-mini
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            openai/gpt-4o-mini
Context Window:   128,000 tokens
Cost:             $0.15/1K tokens
Use For:          Quick fixes, fast reasoning, emergency fallback
```

### 6. DeepSeek R1 (Budget Reasoning) ⭐ RECOMMENDED
```
Profile Name:     clearturn_deepseek-r1
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            deepseek/deepseek-r1
Context Window:   64,000 tokens
Cost:             $0.55/1K tokens
Use For:          Complex governance logic (40% cheaper than Sonnet!)
```

### 7. GLM-4 (Ultra-Budget)
```
Profile Name:     clearturn_glm-4
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            zhipu/glm-4
Context Window:   128,000 tokens
Cost:             $0.30/1K tokens
Use For:          High-volume UI scaffolding, batch generation
```

### 8. Llama 3.1 (405B) (Open Source Alternative)
```
Profile Name:     clearturn_llama-3.1-405b
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            meta/llama-3.1-405b
Context Window:   128,000 tokens
Cost:             $2.00/1K tokens
Use For:          Cost-conscious reasoning tasks
```

### 9. Mixtral 8x22B (Lightweight Reasoning)
```
Profile Name:     clearturn_mixtral-8x22b
API Provider:     OpenAI Compatible
Base URL:         https://gateway.clearturn.tech/v1
API Key:          [same-as-haiku]
Model:            mistral/mixtral-8x22b
Context Window:   65,000 tokens
Cost:             $1.30/1K tokens
Use For:          Medium-complexity code tasks
```

---

## How to Add to Zoo Code Extension

### Step-by-Step Instructions:

1. **Open Zoo Code Settings**
   - Click Zoo Code icon in VS Code sidebar
   - Navigate to: Settings → Providers

2. **Add New Configuration Profile**
   - Click the **[+]** button next to "Configuration Profile"
   - Enter profile name (e.g., `clearturn_deepseek-r1`)

3. **Configure API Settings**
   - **API Provider:** Select "OpenAI Compatible"
   - **Base URL:** `https://gateway.clearturn.tech/v1`
   - **API Key:** Use the same key as your current `clearturn_claude-haiku-4.5` profile
   - **Model:** Enter exact model identifier (e.g., `deepseek/deepseek-r1`)

4. **Save Configuration**
   - Click **Save** button
   - Profile is now available in dropdown

5. **Switch Between Models**
   - Use Configuration Profile dropdown to quickly switch
   - Select based on task complexity (see decision matrix below)

---

## Recommended Configuration Sets

### Set 1: Premium Quality (All Tasks)
Add these 3 profiles:
```
1. clearturn_claude-haiku-4.5      (UI scaffolding)
2. clearturn_claude-sonnet-4       (Complex logic)
3. clearturn_gpt-4o                (Blockers only)

Monthly Cost: ~$210
```

### Set 2: Optimized Cost-Quality ⭐ RECOMMENDED
Add these 3 profiles:
```
1. clearturn_claude-haiku-4.5      (UI scaffolding)
2. clearturn_deepseek-r1           (Complex logic - 40% cheaper!)
3. clearturn_gpt-4o-mini           (Emergency fallback)

Monthly Cost: ~$110-130 (40% savings)
```

### Set 3: Maximum Savings
Add these 3 profiles:
```
1. clearturn_glm-4                 (High-volume UI)
2. clearturn_deepseek-r1           (Strategic tasks)
3. clearturn_gpt-4o-mini           (Quick fixes)

Monthly Cost: ~$60-80 (70% savings)
```

---

## Quick Switching Decision Matrix

Use this guide to choose which profile to switch to:

```
Task: Generate React component (DQRulesTab.jsx)
├─ Simple UI only? → Use: claude-haiku-4.5
├─ Complex state logic? → Use: deepseek-r1 or claude-sonnet-4
└─ Need fastest generation? → Use: gpt-4o-mini

Task: Design DQ validation algorithm
├─ Budget matters? → Use: deepseek-r1 (best value)
├─ Need absolute best? → Use: claude-sonnet-4 or gpt-4o
└─ Ultra-budget? → Use: glm-4

Task: Debug complex issue
├─ Normal debugging? → Use: claude-haiku-4.5
├─ Complex root cause? → Use: deepseek-r1
└─ Critical blocker? → Use: gpt-4o

Task: Write tests
├─ Standard tests? → Use: claude-haiku-4.5 or glm-4
└─ Complex test scenarios? → Use: deepseek-r1
```

---

## Model Selection Keyboard Shortcuts (Recommended)

Configure these keyboard shortcuts in VS Code for fast model switching:

```json
{
  "key": "ctrl+alt+1",
  "command": "zoo.switchProfile",
  "args": "clearturn_claude-haiku-4.5"
},
{
  "key": "ctrl+alt+2",
  "command": "zoo.switchProfile",
  "args": "clearturn_deepseek-r1"
},
{
  "key": "ctrl+alt+3",
  "command": "zoo.switchProfile",
  "args": "clearturn_gpt-4o-mini"
}
```

---

## For Carbon Schema Governance UI Development

### Phase 1: DQ Rules, Governance, Audit History
**Recommended Profile Mix:**
- **70% of time:** `clearturn_claude-haiku-4.5` (component scaffolding)
- **25% of time:** `clearturn_deepseek-r1` (DQ parameter logic, audit diffs)
- **5% of time:** `clearturn_gpt-4o-mini` (quick fixes)

### Phase 2: Quality Metrics & Relations
**Recommended Profile Mix:**
- **60% of time:** `clearturn_claude-haiku-4.5` (UI charting, display)
- **35% of time:** `clearturn_deepseek-r1` (aggregation algorithms)
- **5% of time:** `clearturn_gpt-4o-mini` (emergency)

### Phase 3: Versioning & Archive
**Recommended Profile Mix:**
- **60% of time:** `clearturn_claude-haiku-4.5` (UI components)
- **40% of time:** `clearturn_deepseek-r1` (state machine, locking logic)

---

## Cost Tracking & Budget Alerts

### Monitor Your Usage:
1. Check Zoo Code usage stats (if available)
2. Track token consumption per profile
3. Set mental budget thresholds:
   - **Conservative:** $100-150/month
   - **Balanced:** $150-200/month
   - **Premium:** $200-400/month

### Budget Warning Signs:
- ⚠️ Using `gpt-4o` for routine tasks (switch to cheaper model)
- ⚠️ Using `claude-sonnet-4` for simple UI (switch to Haiku)
- ⚠️ Not leveraging `deepseek-r1` for complex logic (missing 40% savings)

---

## Troubleshooting

### Issue: Model not found
**Solution:** Verify model identifier matches gateway format:
- Format: `provider/model-name`
- Examples: `anthropic/claude-haiku-4.5`, `deepseek/deepseek-r1`

### Issue: API key invalid
**Solution:** Ensure you're using the same API key as your working `clearturn_claude-haiku-4.5` profile

### Issue: Slow responses
**Solution:** 
- DeepSeek R1: Expected for reasoning-heavy tasks
- GLM-4: May be slow on first request (cold start)
- Try `gpt-4o-mini` for fastest responses

### Issue: Quality lower than expected
**Solution:**
- GLM-4 may need more specific prompts (English is second language)
- DeepSeek R1 excels at reasoning but may need clearer problem definitions
- Switch to `claude-sonnet-4` or `gpt-4o` for critical quality

---

## Summary

**Priority Setup (Do This First):**
1. Add `clearturn_deepseek-r1` profile — Best value for complex logic
2. Add `clearturn_gpt-4o-mini` profile — Fast emergency fallback
3. Keep existing `clearturn_claude-haiku-4.5` — Solid default

**Expected Results:**
- **40% cost reduction** vs using only Claude Sonnet 4
- **Maintain 98% quality** for Carbon governance UI tasks
- **Faster iteration** with model switching optimized per task

**Next Steps:**
1. Add DeepSeek R1 profile to Zoo Code
2. Test on DQRuleDialog component generation
3. Compare quality vs Claude Haiku 4.5
4. Use decision matrix to choose profile per task
5. Track costs for first month and adjust strategy
