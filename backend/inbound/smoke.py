# inbound/smoke.py — shared shape for a per-row smoke result (ADR-0060).
#
# Pure helpers: no Django imports, no host-domain words. A cartridge computes its
# own counts and per-row verdicts; these functions assemble the backward-compatible
# envelope (counts + <=20 sample + every reject) plus a full ``results`` list the
# read-only rows viewer joins to the file by 1-based row number.
#
# ``results`` is capped so a pathological CSV cannot bloat the InboundBatch JSON
# field. When the cap is hit the viewer shows "not recorded" honestly instead of
# guessing a verdict.

MAX_SMOKE_RESULTS = 5000
SAMPLE_LIMIT = 20


def issue(field: str, message: str, fix: str) -> dict:
    """One actionable validation failure for a single row.

    ``field`` is the declared target field name (not the source CSV header), so
    the viewer can resolve the column the preparer must change.
    """
    return {'field': field, 'message': message, 'fix': fix}


def row_result(row_no: int, key: str, verdict: str, issues: list | None = None) -> dict:
    """One persisted per-row smoke entry. Clean rows stay small (no ``issues``)."""
    issues = list(issues or [])
    entry = {
        'row': int(row_no),
        'key': key,
        'verdict': verdict,
        'reason': '; '.join(str(item.get('message') or '') for item in issues),
    }
    if issues:
        entry['issues'] = issues
    return entry


def envelope(*, counts: dict, results: list, reject_rows: list, reconcile_preview: dict) -> dict:
    """Assemble the smoke envelope stored on the batch.

    ``results`` is the full per-row list (capped); ``sample`` is the contract's
    <=20 preview and ``reject_rows`` must include every reject regardless of the
    cap so the reject CSV never loses a row.
    """
    env = {
        'insert': int(counts.get('insert') or 0),
        'update': int(counts.get('update') or 0),
        'skip': int(counts.get('skip') or 0),
        'reject': int(counts.get('reject') or 0),
        'sample': list(results[:SAMPLE_LIMIT]),
        'reject_rows': list(reject_rows),
        'reconcile_preview': dict(reconcile_preview or {}),
    }
    if results:
        env['results'] = list(results[:MAX_SMOKE_RESULTS])
        if len(results) > MAX_SMOKE_RESULTS:
            env['results_truncated'] = True
    return env
