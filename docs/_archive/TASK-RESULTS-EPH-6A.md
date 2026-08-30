# EPH-6A — Structured JSON Logging + OpenTelemetry + Prometheus

**Date:** 2026-08-27
**Executor:** master-architect (implemented directly — worker dispatch unavailable)
**Commit:** `8e2e480` (backend)
**Status:** DONE ✅ (verified: 8/8 new tests, 989 passed + 25 subtests regression, live curl)

---

## Summary

Wired the platform's observability layer per P1-10/P1-11:

1. **Structured JSON logging** — the existing `JsonFormatter` now emits a
   `correlation_id` field on every record, injected by a new `CorrelationIdFilter`
   from a thread-local set by `RequestLoggingMiddleware` (EPH-1A). Every log line in
   a request's lifecycle (middleware → views → services) shares one correlation ID.
2. **Prometheus metrics** — new `core/telemetry.py` collectors
   (`carbon_api_requests_total`, `carbon_api_duration_seconds`, `carbon_dq_runs_total`,
   `carbon_ai_conversations_active`) exported via `GET /health/prometheus/`
   (`generate_latest()`), scrapeable over plain HTTP (CB-09 exemption).
3. **OpenTelemetry** — conditional Django auto-instrumentation, active only when
   `OTEL_EXPORTER_OTLP_ENDPOINT` is set (default: disabled, zero overhead).

## Scope

| File | Change |
|------|--------|
| `backend/core/telemetry.py` (NEW) | Prometheus collectors per spec: `Counter` (api_requests_total, dq_runs_total), `Histogram` (api_duration_seconds), `Gauge` (ai_conversations_active) + `app_label_from_path` label helper |
| `backend/core/log_filters.py` (NEW) | `CorrelationIdFilter` + `set_correlation_id`/`clear_correlation_id` thread-local helpers |
| `backend/core/middleware.py` | `RequestLoggingMiddleware`: sets thread-local correlation ID on request, clears on response, records `api_requests_total`/`api_duration_seconds` (metrics endpoints excluded); defensive try/except so telemetry can never break a response |
| `backend/config/settings.py` | `LOGGING`: `correlation_id` filter on console+file handlers, `%(correlation_id)s` in JSON format; `SECURE_REDIRECT_EXEMPT` for `/health/(metrics|prometheus)/` (CB-09); conditional OTel init block |
| `backend/config/health_views.py` | `prometheus_metrics_view` — `HttpResponse(generate_latest(), CONTENT_TYPE_LATEST)` |
| `backend/config/urls.py` | `GET /carbon-api/health/prometheus/` route |
| `backend/dq/services.py` | `dq_runs_total.labels(status=status).inc()` after each `DQResult` create |
| `backend/requirements.txt` | `prometheus-client==0.21.1`, `opentelemetry-api/sdk==1.44.0`, `opentelemetry-instrumentation-django==0.65b0`, `opentelemetry-exporter-otlp==1.44.0` (pinned, installed in venv) |

## Design decisions

1. **`django-prometheus` app skipped.** The spec listed it, but the spec's own
   `telemetry.py` + `generate_latest()` approach makes it unnecessary — the heavier
   wrapper adds an extra middleware + INSTALLED_APPS entry for the same registry.
   Instrumentation is done manually via `RequestLoggingMiddleware` + `dq/services.py`.
2. **OTel gated on env** — `DjangoInstrumentor().instrument()` runs only when
   `OTEL_EXPORTER_OTLP_ENDPOINT` is non-empty; no OTLP pipeline starts otherwise.
3. **CB-09** — `SECURE_REDIRECT_EXEMPT = [rf'^/{api_prefix}/health/(metrics/|prometheus/)']`
   so Prometheus scrapers are not 301-redirected to HTTPS (they do not follow redirects).
   Note: `re.match` anchors at position 0, so the pattern starts with `/`.

## Verification

- `manage.py check` — clean; `makemigrations --check --dry-run` — no changes.
- `pytest core/tests/test_metrics.py -v` — **8/8 passed** (gate: ≥4):
  - prometheus endpoint 200 + `text/plain`
  - body contains `carbon_api_requests_total` and `carbon_api_duration_seconds`
  - legacy `/health/metrics/` still 200 + contains `carbon_database_up`
  - JSON log entry parses with `levelname`/`name`/`message`/`correlation_id`
  - correlation ID injected from thread-local; defaults to `''`; request log carries
    the ID when `X-Correlation-ID` header is sent
- Full regression: **989 passed + 25 subtests** (core, catalog, accounts, mdm, dq, importexport).
- Live (restarted via `./manage.sh restart`):
  - `/carbon-api/health/prometheus/` → 200 `text/plain; version=0.0.4`
    with `carbon_api_requests_total{app="health",method="GET",status="200"} 4.0` etc.
  - `/carbon-api/health/` → 200 `application/json`; `/health/metrics/` → 200; `API-Version: 1` intact.
  - `backend/logs/carbon.log` shows JSON lines with `"correlation_id": "<uuid>"` on `Request completed`.

## Notes for EPH-6B (next)

- Scrape target: `http://127.0.0.1:8009/carbon-api/health/prometheus/` (plain HTTP,
  exempt from HTTPS redirect).
- Grafana datasource: Prometheus; panels for API request rate/latency, DQ run outcomes,
  AI conversations gauge.
- OTel collector (optional): set `OTEL_EXPORTER_OTLP_ENDPOINT` in prod env to enable
  trace export; backend will auto-instrument on restart.
