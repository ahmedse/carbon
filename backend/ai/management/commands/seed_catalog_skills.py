"""Seed ≥1 HRMS skill into the Console Skills Catalog (idempotent, gate-only).

Catalog ``GET /carbon-api/ai/catalog/skills/`` lists skills for
``resolve_instance_id()`` (``nibras`` under ``DJANGO_BRAND=nibras``). A lone
promoted skill on a random PEC-2A test instance UUID does **not** appear.

This command:

  1. Ensures the brand Instance row exists.
  2. Upserts a draft procedure skill on that instance with
     ``app_identifier=resolve_default_app_identifier()`` (``people`` for
     Nibras) and ``visibility=shared``.
  3. Promotes via ``gate._promote_skill`` (admission critics — never a raw
     ``status=instance_promoted`` write).

Marginal-gain eval is disabled for the seed path (same as
``test_pec2a_learning_reuse``) so operators do not need the evals suite.

Usage::

    DJANGO_BRAND=nibras python manage.py seed_catalog_skills
"""

from __future__ import annotations

import asyncio
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ai.instance_registry import resolve_default_app_identifier, resolve_instance_id
from ai.models.base import generate_uuid
from ai.models.core import Instance, Skill

# Stable natural key — re-runs update the same row.
SKILL_NAME = "payroll_run_variance_check"
SKILL_DESCRIPTION = (
    "Check unresolved variance on a Nibras payroll run before commit."
)
SKILL_KIND = "procedure"
SKILL_BODY = {
    "steps": [
        {
            "intent": "Inspect payroll run variance",
            "tool_name": None,
        }
    ]
}


class Command(BaseCommand):
    help = (
        "Seed an HRMS procedure skill on the brand instance and promote it "
        "via the admission gate (idempotent). Run with DJANGO_BRAND=nibras."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--instance",
            default=None,
            help="Engine instance id (default: resolve_instance_id()).",
        )
        parser.add_argument(
            "--name",
            default=SKILL_NAME,
            help=f"Skill name natural key (default: {SKILL_NAME}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print plan without writing or promoting.",
        )

    def handle(self, *args, **options):
        instance_id = options["instance"] or resolve_instance_id()
        skill_name = options["name"]
        app_identifier = resolve_default_app_identifier()
        dry_run = options["dry_run"]

        active_instance = resolve_instance_id()
        if active_instance != instance_id:
            raise CommandError(
                f"Active brand resolves to instance {active_instance!r}, not "
                f"{instance_id!r}. Re-run with DJANGO_BRAND matching that "
                "instance so PLAN_INSTANCE_ID / catalog scope align."
            )

        self.stdout.write(
            f"seed_catalog_skills: instance={instance_id} "
            f"app_identifier={app_identifier} name={skill_name}"
        )

        if dry_run:
            existing = Skill.objects.filter(
                instance_id=instance_id, name=skill_name
            ).first()
            self.stdout.write(
                f"dry-run: instance_exists={Instance.objects.filter(id=instance_id).exists()} "
                f"skill_exists={existing is not None} "
                f"status={getattr(existing, 'status', None)}"
            )
            return

        with transaction.atomic():
            self._ensure_instance(instance_id)
            skill, created = self._upsert_draft(
                instance_id=instance_id,
                name=skill_name,
                app_identifier=app_identifier,
            )

        if skill.status == "instance_promoted" and skill.gate_status == "admitted":
            self.stdout.write(
                self.style.SUCCESS(
                    f"already promoted skill id={skill.id} "
                    f"(created={created}); catalog-ready"
                )
            )
            return

        # Gate path needs pending draft — reset gate_status if a prior reject
        # left the row non-pending without promoting.
        if skill.status == "draft" and skill.gate_status != "pending":
            skill.gate_status = "pending"
            skill.save(update_fields=["gate_status", "updated_at"])

        if skill.status not in ("draft", "user_approved"):
            raise CommandError(
                f"Skill {skill.id} has status={skill.status!r}; "
                "cannot promote via gate (expected draft or user_approved)."
            )

        promoted = self._gate_promote(skill.id)
        self.stdout.write(
            self.style.SUCCESS(
                f"promoted skill id={promoted.id} name={promoted.name} "
                f"status={promoted.status} gate_status={promoted.gate_status} "
                f"(created={created})"
            )
        )

    def _ensure_instance(self, instance_id: str) -> Instance:
        instance, created = Instance.objects.get_or_create(
            id=instance_id,
            defaults={
                "name": instance_id,
                "display_name": instance_id.title(),
                "host_api_url": "/carbon-api/",
                "host_db_url": "",
                "status": "active",
            },
        )
        self.stdout.write(f"instance {instance_id} (created={created})")
        return instance

    def _upsert_draft(
        self, *, instance_id: str, name: str, app_identifier: str
    ) -> tuple[Skill, bool]:
        """Create or refresh a draft skill; never overwrite a promoted row."""
        existing = Skill.objects.filter(
            instance_id=instance_id, name=name
        ).first()
        body_json = json.dumps(SKILL_BODY)
        signature_json = "{}"

        if existing is not None:
            if existing.status == "instance_promoted":
                # Keep CBAC fields correct even if an older seed used carbon/private.
                dirty = False
                if existing.app_identifier != app_identifier:
                    existing.app_identifier = app_identifier
                    dirty = True
                if existing.visibility != "shared":
                    existing.visibility = "shared"
                    dirty = True
                if dirty:
                    existing.save(
                        update_fields=["app_identifier", "visibility", "updated_at"]
                    )
                    self.stdout.write(
                        f"updated CBAC fields on promoted skill {existing.id}"
                    )
                return existing, False

            existing.description = SKILL_DESCRIPTION
            existing.kind = SKILL_KIND
            existing.signature = signature_json
            existing.body = body_json
            existing.app_identifier = app_identifier
            existing.visibility = "shared"
            existing.status = "draft"
            existing.gate_status = "pending"
            existing.author_user_id = existing.author_user_id or "system:seed_catalog_skills"
            existing.save()
            return existing, False

        skill = Skill.objects.create(
            id=generate_uuid(),
            instance_id=instance_id,
            name=name,
            description=SKILL_DESCRIPTION,
            signature=signature_json,
            body=body_json,
            kind=SKILL_KIND,
            status="draft",
            gate_status="pending",
            author_user_id="system:seed_catalog_skills",
            app_identifier=app_identifier,
            visibility="shared",
        )
        return skill, True

    def _gate_promote(self, skill_id: str):
        """Run admission gate → instance_promoted (P1-06)."""
        # Match PEC-2A fixture path: marginal-gain needs evals.stream (absent).
        os.environ["SKILL_GATE_MARGINAL_GAIN_ENABLED"] = "false"
        from ai.engine.core.config import get_settings

        get_settings.cache_clear()

        from ai.engine.skills.gate import _promote_skill
        from ai.store import get_store, reset_store

        reset_store()

        async def _go():
            factory = get_store().get_session_factory()
            async with factory() as db:
                return await _promote_skill(
                    skill_id, db, promoted_by="system:seed_catalog_skills"
                )

        try:
            return asyncio.run(_go())
        except ValueError as exc:
            raise CommandError(f"Admission gate rejected skill: {exc}") from exc
