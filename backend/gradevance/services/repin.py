"""Re-pin AssignmentProfiles / draft Assignments onto a bumped device pack.

Never mutates published summative assignment snapshots in place — creates a
new profile version and only updates *draft* assignments when requested.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml
from django.db import transaction
from django.utils import timezone

from gradevance.models import Assignment, AssignmentProfileRecord, Proposal
from gradevance.services.packs import (
    clear_pack_caches,
    eduos_pack_root,
    find_profile_file_for_id,
    load_profile,
)


class RepinError(Exception):
    pass


def _write_yaml(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


class ProfileRepinService:
    @transaction.atomic
    def repin_from_proposal(
        self,
        proposal: Proposal,
        *,
        base_profile_id: str | None = None,
        base_profile_version: int | None = None,
        update_draft_assignments: bool = True,
    ) -> dict[str, Any]:
        bump = (proposal.payload or {}).get("pack_bump") or {}
        dest_rel = bump.get("dest_rel")
        if not dest_rel:
            raise RepinError("Proposal has no pack_bump.dest_rel — run bump first")

        # Prefer profile context from proposal / bump over NAA default.
        ctx = (proposal.payload or {}).get("profile") or {}
        base_profile_id = (
            base_profile_id
            or ctx.get("pack_id")
            or bump.get("base_profile_id")
            or "naa_cycle1_exam_prep"
        )
        base_profile_version = int(
            base_profile_version
            or ctx.get("version")
            or bump.get("base_profile_version")
            or 1
        )

        fname = find_profile_file_for_id(base_profile_id, base_profile_version)
        loaded = load_profile(fname)
        profile = deepcopy(loaded.profile)
        new_version = int(profile.get("version") or 1) + 1
        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        new_id = f"{profile.get('id') or base_profile_id}_bump"
        profile["id"] = new_id
        profile["version"] = new_version
        profile["status"] = "draft"
        profile["name"] = f"{profile.get('name', new_id)} (device bump {bump.get('new_version')})"
        lct = dict(profile.get("lct_device") or {})
        lct["pack_path"] = dest_rel
        lct["version"] = int(bump.get("new_version") or lct.get("version") or 1)
        profile["lct_device"] = lct
        profile["pipeline"] = {
            **(profile.get("pipeline") or {}),
            "notes": (
                f"Re-pinned to {dest_rel} from proposal {proposal.id} at "
                f"{timezone.now().isoformat()}. Activate for NEW runs only."
            ),
        }

        out_name = f"{new_id}_v{new_version}_{stamp}.yaml"
        out_path = eduos_pack_root() / "profiles" / out_name
        _write_yaml(out_path, profile)

        record, _ = AssignmentProfileRecord.objects.update_or_create(
            pack_id=new_id,
            version=new_version,
            defaults={
                "name": profile["name"],
                "status": "draft",
                "discipline": profile.get("discipline") or "",
                "genre": profile.get("genre") or "",
                "level": profile.get("level") or "",
                "mode": profile.get("mode") or "formative",
                "lct_device_ref": lct,
                "rubric_pack_ref": profile.get("rubric_pack") or {},
                "pipeline_config": profile.get("pipeline") or {},
                "hitl_config": profile.get("hitl") or {},
                "brief": profile.get("brief") or {},
                "source_path": str(out_path),
                "content_hash": bump.get("anchor_id") or "",
            },
        )

        updated_ids: list[str] = []
        if update_draft_assignments:
            drafts = Assignment.objects.filter(
                profile_pack_id=base_profile_id,
                profile_version=base_profile_version,
                status=Assignment.STATUS_DRAFT,
            )
            for asg in drafts:
                asg.profile_pack_id = new_id
                asg.profile_version = new_version
                snap = dict(asg.pipeline_config_snapshot or profile.get("pipeline") or {})
                snap["notes"] = profile["pipeline"].get("notes")
                asg.pipeline_config_snapshot = snap
                asg.save(
                    update_fields=[
                        "profile_pack_id",
                        "profile_version",
                        "pipeline_config_snapshot",
                        "updated_at",
                    ]
                )
                updated_ids.append(str(asg.id))

        proposal.payload = {
            **(proposal.payload or {}),
            "profile_repin": {
                "profile_pack_id": new_id,
                "profile_version": new_version,
                "profile_file": out_name,
                "draft_assignments_updated": updated_ids,
                "repinned_at": timezone.now().isoformat(),
            },
        }
        proposal.save(update_fields=["payload"])
        clear_pack_caches()
        return {
            "profile_pack_id": new_id,
            "profile_version": new_version,
            "profile_file": out_name,
            "record_id": str(record.id),
            "draft_assignments_updated": updated_ids,
            "note": "Published assignments unchanged — new runs must select the new profile.",
        }
