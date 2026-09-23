"""Engineering assurance board. Staff only. Not Pulse Chat and not People.

GET /assurance/report/  — one evaluation of the ledger against the pack.
GET /assurance/stream/  — SSE of that same snapshot. Re-reads the ledger file.
                          Does not run pytest. ?once=1 emits a single frame.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from django.http import StreamingHttpResponse
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from assurance.evaluate import evaluate_packs, load_events  # noqa: E402
from assurance.load import load_brand  # noqa: E402

_DEFAULT_LEDGER = 'docs/assurance/evidence/nibras-demo-2026-09-23.jsonl'


class _IgnoreAcceptNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


def _ledger_path(root: Path, raw: str) -> Path | None:
    text = (raw or '').strip() or _DEFAULT_LEDGER
    candidate = (root / text).resolve()
    if not str(candidate).startswith(str(root.resolve())):
        raise ValueError('ledger path must stay inside the repository')
    return candidate if candidate.is_file() else None


def _head_commit(root: Path) -> str:
    try:
        done = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ''
    if done.returncode != 0:
        return ''
    return (done.stdout or '').strip()


def build_snapshot(root: Path, *, pack: str, commit: str, ledger_raw: str) -> dict:
    packs = load_brand(root, pack)
    ledger = _ledger_path(root, ledger_raw)
    events = load_events(ledger)
    board_commit = commit or _head_commit(root) or 'uncommitted'
    states = {
        (row.pack, row.rule_id): row
        for row in evaluate_packs(packs, events, board_commit)
    }
    rows = []
    blocking_open = 0
    for loaded in packs:
        for rule in loaded.rules:
            state = states[(loaded.id, rule.id)]
            if state.blocking and state.label != 'passed':
                blocking_open += 1
            rows.append({
                'rule_id': rule.id,
                'pack': loaded.id,
                'journey': rule.journey,
                'meaning': rule.meaning,
                'owner': rule.owner,
                'label': state.label,
                'reason': state.reason,
                'blocks_release': rule.blocks_release,
                'residual': rule.residual,
                'implementation': rule.implementation,
                'validation': rule.validation,
            })
    return {
        'pack': pack,
        'commit': board_commit,
        'ledger': str(ledger.relative_to(root)) if ledger else None,
        'rows': rows,
        'blocking_not_passed': blocking_open,
    }


def _frame(payload: dict) -> str:
    return f"data: {json.dumps(payload, sort_keys=True)}\n\n"


def _stream(root: Path, *, pack: str, commit: str, ledger_raw: str, once: bool):
    yield _frame(build_snapshot(root, pack=pack, commit=commit, ledger_raw=ledger_raw))
    if once:
        return
    ledger = _ledger_path(root, ledger_raw)
    last = ledger.stat().st_mtime_ns if ledger and ledger.is_file() else None
    while True:
        time.sleep(5)
        sig = None
        if ledger and ledger.is_file():
            sig = ledger.stat().st_mtime_ns
        if sig != last:
            last = sig
            yield _frame(build_snapshot(root, pack=pack, commit=commit, ledger_raw=ledger_raw))
        else:
            yield ': ping\n\n'


class AssuranceReportView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            payload = build_snapshot(
                _REPO,
                pack=(request.query_params.get('pack') or 'nibras').strip() or 'nibras',
                commit=(request.query_params.get('commit') or '').strip(),
                ledger_raw=(request.query_params.get('ledger') or '').strip(),
            )
        except (FileNotFoundError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(payload)


class AssuranceStreamView(APIView):
    permission_classes = [IsAdminUser]
    content_negotiation_class = _IgnoreAcceptNegotiation

    def get(self, request):
        pack = (request.query_params.get('pack') or 'nibras').strip() or 'nibras'
        commit = (request.query_params.get('commit') or '').strip()
        ledger_raw = (request.query_params.get('ledger') or '').strip()
        once = (request.query_params.get('once') or '').strip() in ('1', 'true')
        response = StreamingHttpResponse(
            _stream(_REPO, pack=pack, commit=commit, ledger_raw=ledger_raw, once=once),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
