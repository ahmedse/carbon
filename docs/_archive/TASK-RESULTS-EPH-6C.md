# TASK-RESULTS-EPH-6C — Freshness Violations Gauge + Prometheus Alert Rules

**Date:** 2026-08-27
**Owner:** Master Architect (direct execution)
**Status:** ✅ DONE
**Closes:** P1-3 follow-up flagged in `TASK-RESULTS-EPH-6B.md` — freshness
observability had no Prometheus gauge; staleness was only visible via in-app
`UserAlert`s, not to the monitoring stack.

---

## Scope

| Deliverable | File | Type |
|---|---|---|
| Freshness collectors | `backend/core/telemetry.py` | Modified |
| Metric recording in freshness pass | `backend/catalog/freshness_service.py` | Modified |
| Metric tests | `backend/catalog/tests/test_freshness_metrics.py` | New |
| Prometheus alert rules | `deploy/carbon/prometheus/carbon-alerts.yml` | New |
| `rule_files` wiring | `deploy/carbon/prometheus/prometheus.yml.example` | Modified |
| Spec + status | `TASKS.md` (EPH-6C spec; EPH-6B stale-details cleanup) | Modified |

## New Metrics

| Metric | Type | Labels |
|---|---|---|
| `carbon_freshness_stale_tables` | Gauge | — |
| `carbon_freshness_tables_total` | Gauge | — |
| `carbon_freshness_alerts_total` | Counter | `severity` |
| `carbon_freshness_table_age_hours` | Gauge | `table_id`, `table` |

## Design Decisions

1. **Gauge `set()` snapshots, not counters** — `check_freshness()` runs as a
   periodic task (cognition supervisor, `COGNITION_FRESHNESS_INTERVAL = 21600s`
   = 6h). Each pass re-`set()`s the stale/total gauges, so a recovered table
   drops back to 0 on the next pass (no monotonic stuck-alert).
2. **Stale = over `max_age_hours` regardless of alert rate-limit** — the stale
   gauge counts a table even when the 6h alert rate-limit suppresses the
   notification, so the metric always reflects true staleness.
3. **Bounded cardinality** — `carbon_freshness_table_age_hours` has one series
   per *enabled policy* (not per row), keeping the label set small.
4. **Shared-registry test pattern** — `prometheus_client`'s default registry is
   process-global and persists across tests; alert-counter assertions use
   `REGISTRY.get_sample_value(...)` **deltas** rather than absolute values.
5. **Alert rules as files** (`carbon-alerts.yml`): `CarbonStaleDataTable`
   (stale > 0 for 15m, warning) + `CarbonAPIErrorRateHigh` (5xx share > 5% for
   10m, critical, with `clamp_min` guard against div-by-zero). VPS operator
   wires `rule_files: ['/etc/prometheus/rules/*.yml']` and points Alertmanager
   receivers at their channel.

## Verification Evidence

```
# 1. Django check — clean
System check identified no issues (0 silenced).

# 2. New tests — 5/5 pass
catalog/tests/test_freshness_metrics.py ..... [100%] 5 passed in 1.94s

# 3. Regression (freshness + telemetry suites) — 18/18 pass
catalog/tests/test_freshness.py
catalog/tests/test_freshness_metrics.py
core/tests/test_metrics.py
.................. [100%] 18 passed in 3.20s

# 4. Live export — all 4 families present (values populate on the next
#    in-process freshness pass; dev shell run verified {checked: 1, alerted: 1})
curl -s http://localhost:8009/carbon-api/health/prometheus/ | grep carbon_freshness
carbon_freshness_stale_tables 0.0
carbon_freshness_tables_total 0.0
# HELP carbon_freshness_alerts_total / TYPE counter
# HELP/TYPE carbon_freshness_table_age_hours
```

> Note: the dev server exports `0.0` until a freshness pass executes **inside
> the server process** (supervisor loop every 6h). A one-off shell
> `check_freshness()` ran in a separate process and confirmed the service
> logic (`{'checked': 1, 'alerted': 1, 'skipped': 0}` with a seeded stale
> table); the unit tests assert non-zero in-process values directly.

## Alert Rules Shipped

| Alert | Expr | For | Severity |
|---|---|---|---|
| `CarbonStaleDataTable` | `carbon_freshness_stale_tables > 0` | 15m | warning |
| `CarbonAPIErrorRateHigh` | 5xx share via `rate(...,status=~"5..")[5m]` / `clamp_min(rate(...),1) * 100 > 5` | 10m | critical |

## Notes / Follow-ups

- Grafana panels can now be added for freshness (e.g., "Tables with stale
  data" list via `carbon_freshness_table_age_hours > 24`), reusing the
  EPH-6B `carbon-dq.json` dashboard. Not added now — EPH-6B dashboard set
  already shipped; adding panels is a VPS-side import.
- EPH-6B spec stale details in `TASKS.md` corrected in this commit
  (port `8006` prod / `8009` dev, `/carbon-api/health/prometheus/` path,
  `config/health_views.py`).
