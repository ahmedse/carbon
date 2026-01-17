# AI Copilot Engine Plan (2026)

**Goal:** Build a truly helpful, production-grade Carbon AI engine aligned to the platform vision: accurate, proactive, compliant, and action-oriented.

**Status:** Phase 1 in progress (Jan 17, 2026)

---

## Phase 1 — Foundation Stabilization (Week 1)
**Objective:** Make the MVP reliable and consistent end-to-end.

**Deliverables**
- Align models, serializers, and API payloads
- Token tracking + cost estimation consistency
- Resolve frontend/backend contract mismatches
- Clarify limitations (no streaming yet) in docs

**Exit Criteria**
- Chat works end-to-end with consistent IDs and timestamps
- Preferences and insights render without field errors
- Basic telemetry visible in logs

---

## Phase 2 — Knowledge & RAG Hardening (Weeks 2–3)
**Objective:** Trustworthy, citeable knowledge layer.

**Deliverables**
- Curated sources (GHG Protocol, ISO 14064, CSRD/ESRS)
- Source citations returned with answers
- Versioned knowledge ingestion pipeline
- RAG evaluation set + retrieval tuning

---

## Phase 3 — Core Agents (Weeks 4–6)
**Objective:** Real assistance, not just chat.

**Deliverables**
- Data Orchestrator (validation, missing data, outliers)
- Report Intelligence (narrative + charts)
- Compliance Guardian (gap checks)
- Tool routing in Copilot (actions + workflows)

---

## Phase 4 — Actions & Workflows (Weeks 7–8)
**Objective:** AI that acts safely.

**Deliverables**
- Calculations tooling (scopes, factors, QA)
- Report generation pipeline (draft → review → export)
- Controlled actions (create tasks, open data entry)
- Confirmation steps for risky actions

---

## Phase 5 — Proactive Intelligence (Weeks 9–10)
**Objective:** Insight engine that anticipates needs.

**Deliverables**
- Scheduled insight generation
- Alerts for deadlines, anomalies, missing data
- Relevance scoring + user-level filters

---

## Phase 6 — Quality, Safety, and Scale (Weeks 11–12)
**Objective:** Stable and measurable quality.

**Deliverables**
- Gold-set evaluation (accuracy, compliance, completeness)
- Load testing and cost optimization
- Monitoring, tracing, and alerting

---

## Current Work (Phase 1)
- Contract fixes (models/serializers/views)
- Token tracking migration
- Frontend adjustments for IDs/timestamps
- Documentation consistency pass

---

## Success Metrics
- ≥95% accurate retrieval in evaluation set
- ≥90% “helpful” rating in internal tests
- <3s median response time (non-streaming)
- <1% error rate in chat and insights
