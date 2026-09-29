"""Turn saved smoke envelopes into a series. Callers pass the path. Tests use tmp."""
import json
from pathlib import Path

_COUNTS = ('insert', 'update', 'skip', 'reject')


def smoke_series_row(batch) -> dict:
    """One row. Counts come from the envelope already stored on the batch."""
    smoke = batch.smoke or {}
    when = batch.updated_at
    date = when.date().isoformat() if when is not None else ''
    row = {
        'date': date,
        'batch_id': batch.id,
        'status': batch.status,
        'target_key': batch.target_key,
    }
    for name in _COUNTS:
        row[name] = int(smoke.get(name) or 0)
    return row


def write_smoke_series(path, batches) -> None:
    payload = {'schema': 1, 'rows': [smoke_series_row(batch) for batch in batches]}
    Path(path).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


SERIES_LIMIT = 10
SERIES_STATUSES = ('smoked', 'committed')


def series_batches(limit: int = SERIES_LIMIT):
    """Newest smoked or committed batches whose smoke envelope is a dict.

    Drafts, failures, and empty envelopes are omitted. The caller writes the
    file. This function does not.
    """
    from inbound.models import InboundBatch

    chosen = []
    rows = InboundBatch.objects.filter(status__in=SERIES_STATUSES).order_by('-id')
    for batch in rows.iterator():
        if isinstance(batch.smoke, dict) and batch.smoke:
            chosen.append(batch)
        if len(chosen) >= limit:
            break
    return chosen
