"""Sync AssignmentProfile YAML catalogs into AssignmentProfileRecord rows."""
from __future__ import annotations

import hashlib

from django.core.management.base import BaseCommand

from gradevance.models import AssignmentProfileRecord
from gradevance.services.packs import eduos_pack_root, list_profiles, load_profile


class Command(BaseCommand):
    help = "Sync domain_packs/eduos profiles into AssignmentProfileRecord (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Delete DB rows whose pack_id@version is no longer on disk.",
        )

    def handle(self, *args, **options):
        root = eduos_pack_root()
        n = 0
        seen: set[tuple[str, int]] = set()
        for meta in list_profiles():
            loaded = load_profile(meta["file"])
            profile = loaded.profile
            content = (root / "profiles" / meta["file"]).read_bytes()
            digest = hashlib.sha256(content).hexdigest()[:16]
            pack_id = profile["id"]
            version = int(profile.get("version") or 1)
            seen.add((pack_id, version))
            AssignmentProfileRecord.objects.update_or_create(
                pack_id=pack_id,
                version=version,
                defaults={
                    "name": profile.get("name") or profile["id"],
                    "status": profile.get("status") or "validated",
                    "discipline": profile.get("discipline") or "",
                    "genre": profile.get("genre") or "",
                    "level": profile.get("level") or "",
                    "mode": profile.get("mode") or "formative",
                    "lct_device_ref": profile.get("lct_device") or {},
                    "rubric_pack_ref": profile.get("rubric_pack") or {},
                    "pipeline_config": profile.get("pipeline") or {},
                    "hitl_config": profile.get("hitl") or {},
                    "brief": profile.get("brief") or {},
                    "source_path": str(loaded.source_path),
                    "content_hash": digest,
                },
            )
            n += 1
        pruned = 0
        if options.get("prune"):
            for row in AssignmentProfileRecord.objects.all():
                if (row.pack_id, row.version) not in seen:
                    row.delete()
                    pruned += 1
        msg = f"Synced {n} AssignmentProfileRecord(s)."
        if pruned:
            msg += f" Pruned {pruned}."
        self.stdout.write(self.style.SUCCESS(msg))
