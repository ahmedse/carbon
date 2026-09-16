# PEC-3A — Proactive delivery API proof

**Date:** 2026-09-16  
**Worker:** backend-worker  
**Scope:** `proactive/delivery.py` → persist `KgProactiveInsight` → `GET /carbon-api/ai/insights/` + `GET .../stream/` (SSE). No frontend.

## Trace (proactive → persist → list/SSE)

```
run_proactive_evaluation / deliver_insight
  → build_outcome_fields (confidence + provenance, RULE_23 sanitize)
  → KgProactiveInsight(visibility=shared, app_identifier=brand-aware)
  → db.commit
  → _deliver → _push_websocket
       → Redis bus frame event_type=insight.new (ALL severities, incl. info/digest)
       → optional Notification for warning/critical
  → InsightsListView._serialize_insight  (lifts confidence/provenance)
  → InsightsStreamView SSE  (filters CBAC via _frame_visible, strips partition keys)
```

## Gaps fixed

| Gap | Fix |
|-----|-----|
| List/SSE had no honest confidence or provenance | `build_outcome_fields` / `extract_outcome_fields`; list + bus frame lift `confidence`, `confidence_label`, `provenance` |
| `info`/digest skipped bus publish → SSE silent | `_deliver` always calls `_push_websocket` (notifications still severity-gated) |
| Frame `app_identifier` fell back to `instance_id` (broke Nibras SSE vs `people`) | `_resolve_app_identifier` via `default_app_for_instance`; engine dataclass carries `app_identifier` |
| `scope_ai_queryset` hardcoded `carbon` | Uses `resolve_default_app_identifier()` so list matches SSE brand partition |
| Raw context leaked `trigger_summary` / SQL | Internal keys stripped before persist/API |

## Sample OUTCOME (list serialize)

```json
{
  "id": "demo-insight-1",
  "title": "Payroll run 12 has an unresolved variance",
  "narrative": "Run 12 still shows an unresolved variance against the posted ledger — review before close.",
  "severity": "warning",
  "insight_type": "threshold_alert",
  "recommended_actions": ["Open payroll run 12", "Resolve variance"],
  "context": {
    "measured": {"value": 1250.0, "metric": "variance_amount", "unit": "KWD"},
    "related_alert_count": 1
  },
  "confidence": 0.8,
  "confidence_label": "high",
  "provenance": {
    "sources": [
      {"label": "Live reading", "detail": "value=1250.0, metric=variance_amount, unit=KWD"},
      {"label": "Recent alerts", "detail": "1 related alert(s) in the last day"}
    ],
    "basis": "Based on live readings and recent alerts"
  },
  "disposition": "pending",
  "created_at": "2026-09-16T00:00:00+00:00"
}
```

Confidence conservation: no measured reading → prior capped at `0.55` (`medium`/`low`/`uncertain`), never amplified to `high`.

RULE_23: wire payload must not contain `trigger_id`, `delivery_channel`, `trigger_summary`, SQL, witness/salience jargon.

## Verification

```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "proactive or insight" -q --maxfail=8 --disable-warnings
# 65 passed, 2114 deselected

./.ai-toolkit/scripts/verify.sh backend
# ✓ django check / ✓ no missing migrations / GATE PASSED
```

## Files touched

| File | Change |
|------|--------|
| `backend/ai/engine/proactive/delivery.py` | Outcome builders; always bus-publish; brand app_identifier |
| `backend/ai/engine/knowledge_graph/models.py` | `app_identifier` / org / host on engine dataclass |
| `backend/ai/insights_api.py` | Serialize + SSE OUTCOME with confidence/provenance |
| `backend/accounts/ai_scoping.py` | Brand-aware `app_identifier` filter |
| `backend/ai/tests/test_insights_api.py` | PEC-3A coverage |

Frontend notification chrome intentionally untouched (PEC-3B).
