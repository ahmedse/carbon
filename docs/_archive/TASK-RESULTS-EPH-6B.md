# EPH-6B — Grafana Dashboards + Prometheus Scrape Config

**Date:** 2026-08-27
**Executor:** master-architect (implemented directly — devops-worker dispatch unavailable)
**Commit:** `37f3977`
**Status:** DONE ✅ (dashboards validated against live export; VPS apply documented as manual gate)

---

## Summary

Added the observability UI layer on top of EPH-6A's metrics endpoint:

1. **`carbon-api.json`** — API traffic/latency/errors dashboard (request rate by app and
   status, latency P50/P95/P99 via `histogram_quantile`, error rate with a legacy alert
   rule `> 5% for 5m`, active AI conversations, total requests).
2. **`carbon-dq.json`** — DQ quality dashboard (runs/24h, per-hour stacked pass/fail/
   skipped bars, failure rate %, DQ runs total by status, quality-violations proxy panel,
   Infinity JSON panel for the DQ summary API).
3. **`prometheus.yml.example`** — documented VPS scrape config addition (CB-09-safe:
   plain HTTP + `/carbon-api/health/prometheus/`).

## Scope

| File | Change |
|------|--------|
| `deploy/carbon/grafana/dashboards/carbon-api.json` (NEW) | 10 PromQL queries, 8 panels, alert `error_rate > 5% for 5m`, uid `carbon-api-eph6b` |
| `deploy/carbon/grafana/dashboards/carbon-dq.json` (NEW) | 5 PromQL queries + 1 Infinity JSON panel, uid `carbon-dq-eph6b` |
| `deploy/carbon/prometheus/prometheus.yml.example` (NEW) | `carbon-backend` job: `targets: ['127.0.0.1:8006']` (prod) / `8009` (dev), `metrics_path: /carbon-api/health/prometheus/`, `scheme: http` |

## Design decisions & corrections

1. **Port correction (spec → reality).** Spec's scrape target used `127.0.0.1:8009`
   (the dev port). Production backend binds `127.0.0.1:8006` (host → container :8000).
   The example documents both, defaulting to prod `8006`.
2. **Freshness violations panel is a documented proxy.** No dedicated freshness metric
   exists yet — the panel plots failed DQ runs and the description flags it. A real
   `carbon_freshness_violations` gauge is a small follow-up (wire `check_freshness()`
   output), deliberately NOT in scope to avoid creep.
3. **Scorecard panel uses the Infinity datasource** (`marcalexiei.infinity-panel`)
   against `GET /carbon-api/dq/metrics/` (table_count/total_rows/completeness_pct).
   Notes for the VPS operator: the Infinity plugin must be installed, and the endpoint
   is JWT-gated (`IsAuthenticated`) — configure a service token/Authorization header in
   the datasource. Per-table scorecards live at `/carbon-api/dq/tables/<id>/scorecard/`.
4. **All Prometheus panels work out of the box** — every referenced metric family was
   confirmed in the live export (`carbon_api_requests_total` counter,
   `carbon_api_duration_seconds` histogram with 135 bucket series,
   `carbon_dq_runs_total` counter, `carbon_ai_conversations_active` gauge, plus
   `process_*`/`python_*` runtime metrics).

## Verification

- Both dashboard JSON files parse (`json.load` OK), 15 PromQL queries total listed.
- Live export at `http://localhost:8009/carbon-api/health/prometheus/` contains every
  metric family the dashboards query (incl. histogram buckets for the quantile queries).
- `carbon_dq_runs_total` series appears only after the first DQ run `inc()` — expected;
  DQ dashboards will populate as rules execute.
- **VPS gate (manual, per user rule — no docker/VPS in dev):**
  ```bash
  # On VPS — apply scrape target:
  #   copy the carbon-backend job from deploy/carbon/prometheus/prometheus.yml.example
  #   into /etc/prometheus/prometheus.yml, then:
  sudo systemctl reload prometheus
  # Verify:
  curl -s http://127.0.0.1:8006/carbon-api/health/prometheus/ | head -5   # text format, no redirect
  # Grafana: import the two JSON dashboards (Dashboard → New → Import).
  #   Select the Prometheus datasource for ${DS_PROMETHEUS}.
  #   Install the Infinity plugin for the DQ summary panel (optional).
  ```

## Notes for follow-ups

- EPH-6C candidate: `carbon_freshness_violations` gauge wired into `check_freshness()`
  + a real alert rule (unified alerting) for stale tables.
- Alert delivery: Grafana unified alerting → notification policy (email/webhook) is a
  VPS-side config, not in repo.
