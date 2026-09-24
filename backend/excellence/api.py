"""Excellence Ledger API (ADR-0051 P1–P2). Staff only.

GET  /excellence/ladder/?tier=&track=
GET  /excellence/subjects/<id>/
GET  /excellence/stream/?tier=&once=1
POST /excellence/runs/                 trigger collectors (repo / pulse_gauge / antipatterns / pytest:one-app)
GET  /excellence/runs/                 recent runs
POST /excellence/exemptions/           grant an exemption (expires)
DELETE /excellence/exemptions/<id>/    revoke
"""
from __future__ import annotations

import json
import time
from datetime import date

from django.db import DatabaseError
from django.http import StreamingHttpResponse
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .catalogue import LEVEL_NAMES, load_catalogue
from .evaluator import evaluate
from .gauge import head_commit
from .models import Event, Exemption, Run, Snapshot
from .runs import UI_SAFE, execute_run, run_as_dict

_LEDGER_DOWN = 'Excellence ledger database is not reachable in this deployment.'


def _latest_event_id() -> int:
    row = Event.objects.order_by('-id').values_list('id', flat=True).first()
    return int(row or 0)


def _tiers(cat) -> list[dict]:
    out = []
    for tier in sorted(cat.tiers.values(), key=lambda t: (t.id != 'platform', t.id)):
        out.append({
            'id': tier.id,
            'title': tier.title,
            'owner': tier.owner,
            'level_names': list(tier.level_names),
            'tracks': [
                {'id': tr.id, 'title': tr.title, 'owner': tr.owner}
                for (tid, _), tr in sorted(cat.tracks.items())
                if tid == tier.id
            ],
        })
    return out


def build_ladder(tier: str | None = None, track: str | None = None) -> dict:
    cat = load_catalogue()
    head = head_commit()
    qs = Event.objects.all()
    if tier:
        qs = qs.filter(tier=tier)
    events = list(qs.values('check_id', 'subject_id', 'commit', 'result', 'evidence_class', 'at', 'source'))
    exemptions = list(Exemption.objects.values('check_id', 'subject_id', 'until'))
    reports = evaluate(cat, events, exemptions, head=head, tier=tier, track=track)
    subjects = []
    for rep in reports.values():
        row = rep.as_dict()
        row['title'] = rep.subject.title
        row['owner'] = rep.subject.owner
        row['level_name'] = LEVEL_NAMES[rep.level]
        row['counts'] = _state_counts(row['checks'])
        row.pop('checks')
        subjects.append(row)
    return {
        'head': head,
        'latest_event_id': _latest_event_id(),
        'problems': cat.problems,
        'tiers': _tiers(cat),
        'subjects': subjects,
        'ui_collectors': sorted(UI_SAFE),
    }


def _state_counts(checks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in checks:
        counts[c['state']] = counts.get(c['state'], 0) + 1
    return counts


def build_subject(subject_id: str) -> dict | None:
    cat = load_catalogue()
    subject = cat.subjects.get(subject_id)
    if subject is None:
        return None
    head = head_commit()
    events = list(
        Event.objects.filter(subject_id=subject_id)
        .order_by('-at')
        .values('id', 'check_id', 'subject_id', 'commit', 'result', 'evidence_class', 'at', 'source', 'runner', 'duration_ms', 'detail')
    )
    exemptions = list(
        Exemption.objects.filter(subject_id=subject_id)
        .values('id', 'check_id', 'subject_id', 'until', 'reason', 'granted_by')
    )
    rep = evaluate(cat, events, exemptions, head=head, tier=subject.tier, track=subject.track or None)[subject_id]
    trend = list(
        Snapshot.objects.filter(subject_id=subject_id).order_by('-date').values('date', 'level', 'commit', 'dimensions')[:60]
    )
    body = rep.as_dict()
    body.update({
        'title': subject.title,
        'owner': subject.owner,
        'level_name': LEVEL_NAMES[rep.level],
        'paths': list(subject.paths),
        'tests': list(subject.tests),
        'spec': list(subject.spec),
        'adr': list(subject.adr),
        'head': head,
        'events': [{**e, 'at': e['at'].isoformat() if e['at'] else None} for e in events[:100]],
        'exemptions': [{**x, 'until': x['until'].isoformat()} for x in exemptions],
        'trend': [{**t, 'date': t['date'].isoformat()} for t in trend],
    })
    return body


class _IgnoreAcceptNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


def _param(request, name: str) -> str | None:
    return (request.query_params.get(name) or '').strip() or None


class LadderView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            return Response(build_ladder(_param(request, 'tier'), _param(request, 'track')))
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)


class SubjectView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, subject_id: str):
        try:
            body = build_subject(subject_id)
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)
        if body is None:
            return Response({'detail': f'No subject {subject_id} in the catalogue.'}, status=404)
        return Response(body)


def _frame(payload: dict) -> str:
    return f"data: {json.dumps(payload, sort_keys=True, default=str)}\n\n"


def _stream(tier: str | None, track: str | None, once: bool):
    snap = build_ladder(tier, track)
    yield _frame(snap)
    if once:
        return
    last = snap['latest_event_id']
    while True:
        time.sleep(5)
        current = _latest_event_id()
        if current != last:
            last = current
            yield _frame(build_ladder(tier, track))
        else:
            yield ': ping\n\n'


class StreamView(APIView):
    permission_classes = [IsAdminUser]
    content_negotiation_class = _IgnoreAcceptNegotiation

    def get(self, request):
        try:
            _latest_event_id()
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)
        once = (request.query_params.get('once') or '').strip() in ('1', 'true')
        response = StreamingHttpResponse(
            _stream(_param(request, 'tier'), _param(request, 'track'), once),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class RunListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            rows = Run.objects.all()[:50]
            return Response({'runs': [run_as_dict(r) for r in rows]})
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        collectors = data.get('collectors') or []
        if isinstance(collectors, str):
            collectors = [collectors]
        try:
            run = execute_run(
                collectors=list(collectors),
                requested_by=getattr(request.user, 'username', '') or 'staff',
                tier=str(data.get('tier') or '').strip(),
                track=str(data.get('track') or '').strip(),
                run_apps=list(data.get('run_apps') or []),
                run_vitest=list(data.get('run_vitest') or []),
                write_snapshot=bool(data.get('write_snapshot')),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)
        status = 201 if run.status == 'succeeded' else 200
        return Response(run_as_dict(run, include_ladder=True), status=status)


class ExemptionListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        check_id = str(data.get('check_id') or '').strip()
        subject_id = str(data.get('subject_id') or '').strip()
        reason = str(data.get('reason') or '').strip()
        until_raw = str(data.get('until') or '').strip()
        if not (check_id and subject_id and reason and until_raw):
            return Response(
                {'detail': 'check_id, subject_id, reason, and until (YYYY-MM-DD) are required.'},
                status=400,
            )
        cat = load_catalogue()
        if subject_id not in cat.subjects:
            return Response({'detail': f'Unknown subject {subject_id}.'}, status=404)
        if check_id not in cat.checks:
            return Response({'detail': f'Unknown check {check_id}.'}, status=404)
        try:
            until = date.fromisoformat(until_raw)
        except ValueError:
            return Response({'detail': 'until must be YYYY-MM-DD.'}, status=400)
        if until < date.today():
            return Response({'detail': 'until must be today or later.'}, status=400)
        try:
            row = Exemption.objects.create(
                check_id=check_id,
                subject_id=subject_id,
                reason=reason,
                granted_by=getattr(request.user, 'username', '') or 'staff',
                until=until,
            )
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)
        return Response({
            'id': row.pk,
            'check_id': row.check_id,
            'subject_id': row.subject_id,
            'reason': row.reason,
            'granted_by': row.granted_by,
            'until': row.until.isoformat(),
        }, status=201)


class ExemptionDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, exemption_id: int):
        try:
            deleted, _ = Exemption.objects.filter(pk=exemption_id).delete()
        except DatabaseError:
            return Response({'detail': _LEDGER_DOWN}, status=503)
        if not deleted:
            return Response({'detail': 'Exemption not found.'}, status=404)
        return Response(status=204)
