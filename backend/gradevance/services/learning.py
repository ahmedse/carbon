"""P2 seam: mine ExpertEdit stream into Proposal candidates (RULE_32).

Promotion still requires professor/QA accept + reliability gate before any
pack bump. This miner only clusters edits into draft proposals.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from gradevance.models import ExpertEdit, Proposal


class ProposalMiner:
    """Cluster recent ExpertEdits into draft Proposals by kind+direction."""

    def mine(self, edits: Iterable[ExpertEdit] | None = None) -> list[Proposal]:
        qs = edits
        if qs is None:
            qs = ExpertEdit.objects.order_by("-created_at")[:500]
        buckets: dict[tuple, list[ExpertEdit]] = defaultdict(list)
        for edit in qs:
            key = self._bucket_key(edit)
            if key:
                buckets[key].append(edit)
        created: list[Proposal] = []
        with transaction.atomic():
            for key, group in buckets.items():
                if len(group) < 1:
                    continue
                # Skip if an open proposal already covers these edits.
                edit_ids = [str(e.id) for e in group]
                existing = Proposal.objects.filter(
                    kind=key[0],
                    status__in=[Proposal.STATUS_DRAFT, Proposal.STATUS_PROPOSED],
                )
                skip = False
                for prop in existing:
                    if set(edit_ids) & set(prop.source_edit_ids or []):
                        skip = True
                        break
                if skip:
                    continue
                payload = self._payload_for(key, group)
                prop = Proposal.objects.create(
                    kind=key[0],
                    status=Proposal.STATUS_DRAFT,
                    payload=payload,
                    source_edit_ids=edit_ids,
                )
                created.append(prop)
        return created

    def _bucket_key(self, edit: ExpertEdit) -> tuple | None:
        after = edit.after or {}
        if edit.edit_kind == ExpertEdit.KIND_LCT:
            return (
                "anchor",
                after.get("dimension"),
                after.get("value"),
            )
        if edit.edit_kind == ExpertEdit.KIND_RUBRIC:
            return (
                "rubric_note",
                after.get("criterion_id"),
                after.get("band"),
            )
        if edit.edit_kind == ExpertEdit.KIND_COACHING:
            return ("action_template", after.get("id") or "coaching")
        if edit.edit_kind == ExpertEdit.KIND_SEGMENT:
            # Cluster by segment count + stage set — promote to segmentation policy.
            segs = after.get("segments") or []
            stages = tuple(sorted({(s.get("stage_guess") or "what") for s in segs}))
            return ("segmentation_policy", len(segs), stages)
        return None

    def _payload_for(self, key: tuple, group: list[ExpertEdit]) -> dict:
        kind = key[0]
        sample = group[0].after or {}
        return {
            "kind": kind,
            "cluster_key": list(key),
            "edit_count": len(group),
            "sample_after": sample,
            "sample_rationale": group[0].rationale,
            "mined_at": timezone.now().isoformat(),
            "activation": "requires_professor_accept_and_kappa_gate",
        }
