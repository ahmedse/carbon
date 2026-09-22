"""Seed Nibras ProcessDefinition + Capability rows (Pulse governance).

Loads ``domain_packs/nibras`` into durable governance rows so the AI coworker
follows deterministic, admin-governed lifecycle processes instead of
improvising:

  * ``Capability`` rows — one per governed host action in the pack's
    ``api_catalog.yaml`` ``capabilities:`` list (upserted, ``app_identifier``
    = brand default app via ``resolve_default_app_identifier()``, i.e.
    ``people`` for Nibras — matches ``scope_ai_queryset``). Each is validated
    fail-closed against ``ai.capability_registry`` at load time.
    * ``ProcessDefinition`` rows for ``payroll.run.lifecycle``,
        ``leave.request.lifecycle``, ``loan.request.lifecycle``,
        ``gosi_wps.sif.lifecycle``, and ``employee.onboarding.lifecycle``
        (via ``pec5b_onboarding_process_ids``) — each created as a draft and
        driven draft → review → active through ``ai.registry_service``
        (author submits, a distinct publisher publishes).

Idempotent: re-running upserts capabilities and leaves already-active process
definitions untouched; partially-seeded processes are driven the rest of the
way to active. Additive only — no destructive DB ops.

Run under the Nibras brand so the pack + capability registry resolve to Nibras::

    DJANGO_BRAND=nibras python manage.py seed_nibras_processes
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.constants import AI_PROCESS_OWNER_GROUP, AI_PUBLISHER_GROUP
from accounts.models import ScopedRole, User
from ai.engine.ports.domain import load_domain_pack
from ai.instance_registry import resolve_default_app_identifier, resolve_instance_id
from ai.models.capability import Capability, load_capabilities
from ai.models.process import STATUS_ACTIVE, STATUS_DRAFT, STATUS_REVIEW
from ai.registry_service import ProcessRegistry, RegistryNotFoundError

# System governance identities for the seed (author ≠ publisher — the
# separation-of-duties guarantee the registry enforces at publish time).
AUTHOR_USERNAME = "nibras-process-seed"
PUBLISHER_USERNAME = "nibras-process-publisher"

def pec5b_onboarding_process_ids() -> tuple[str, ...]:
    """PEC-5B additive process ids (keep separate from PEC-5A edits)."""
    return ("employee.onboarding.lifecycle",)


PROCESS_IDS = (
    "payroll.run.lifecycle",
    "leave.request.lifecycle",
    "loan.request.lifecycle",
    "gosi_wps.sif.lifecycle",
    "attendance.permission.lifecycle",
) + pec5b_onboarding_process_ids()

# Fields copied onto each upserted Capability row (mirrors the pack spec).
_CAPABILITY_FIELDS = (
    "business_name",
    "purpose",
    "kind",
    "inputs",
    "preconditions",
    "permissions",
    "effects",
    "side_effects",
    "approval_requirements",
    "requires_confirmation",
    "idempotency",
    "verification",
    "failure_semantics",
    "recovery",
    "owner",
    "version",
    "host_action",
)


class Command(BaseCommand):
    help = (
        "Seed Nibras payroll/leave/loan/GOSI-WPS/onboarding/attendance ProcessDefinition + "
        "Capability rows from domain_packs/nibras (idempotent). "
        "Run with DJANGO_BRAND=nibras."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--instance",
            default="nibras",
            help="Engine instance id for pack resolve (default: nibras).",
        )

    def handle(self, *args, **options):
        instance_id = options["instance"]

        pack_dir = Path(settings.BASE_DIR).parent / "domain_packs" / instance_id
        if not pack_dir.is_dir():
            raise CommandError(f"Domain pack directory not found: {pack_dir}")

        active_instance = resolve_instance_id()
        if active_instance != instance_id:
            raise CommandError(
                f"Active brand resolves to instance {active_instance!r}, not "
                f"{instance_id!r}. Re-run with DJANGO_BRAND={instance_id} so the "
                "capability registry and process validator resolve this pack."
            )

        pack = load_domain_pack(pack_dir)

        with transaction.atomic():
            cap_created, cap_updated = self._seed_capabilities(pack)
            process_status = self._seed_processes(pack)

        self.stdout.write(
            self.style.SUCCESS(
                f"Nibras process seed complete — capabilities: "
                f"{cap_created} created, {cap_updated} updated; "
                f"processes: {process_status}."
            )
        )

    # ── Capabilities ──────────────────────────────────────────────────

    def _seed_capabilities(self, pack) -> tuple[int, int]:
        """Upsert the pack's capabilities as ``Capability`` rows (fail-closed)."""
        created = 0
        updated = 0
        # CBAC list API filters by resolve_default_app_identifier() (people for
        # Nibras), not the engine instance id — same contract as seed_nibras_knowledge.
        app_identifier = resolve_default_app_identifier()
        for cap in load_capabilities(pack):  # validates host_action fail-closed
            defaults = {field: getattr(cap, field) for field in _CAPABILITY_FIELDS}
            defaults["app_identifier"] = app_identifier
            defaults["visibility"] = "shared"
            _, was_created = Capability.objects.update_or_create(
                capability_id=cap.capability_id, defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    # ── Process definition ────────────────────────────────────────────

    def _seed_processes(self, pack) -> str:
        """Create + publish all lifecycle processes via the registry."""
        statuses = [
            f"{process_id!r}={self._seed_process(pack, process_id)}"
            for process_id in PROCESS_IDS
        ]
        return ", ".join(statuses)

    def _seed_process(self, pack, process_id: str) -> str:
        """Create + publish one lifecycle process via the registry (idempotent)."""
        document = next(
            (dict(p) for p in pack.processes() if p.get("id") == process_id), None,
        )
        if document is None:
            raise CommandError(
                f"Process {process_id!r} not found in the Nibras domain pack."
            )

        registry = ProcessRegistry()
        try:
            current = registry.resolve(process_id)
        except RegistryNotFoundError:
            current = None

        if current is not None and current.status == STATUS_ACTIVE:
            return "already active (unchanged)"

        author = self._ensure_system_user(AUTHOR_USERNAME, AI_PROCESS_OWNER_GROUP)
        publisher = self._ensure_system_user(PUBLISHER_USERNAME, AI_PUBLISHER_GROUP)

        if current is None:
            registry.create_draft(document, author=author)
            current = registry.resolve(process_id)

        if current.status == STATUS_DRAFT:
            registry.submit_for_review(process_id, author)
            current = registry.resolve(process_id)
        if current.status == STATUS_REVIEW:
            registry.publish(process_id, publisher)
            current = registry.resolve(process_id)

        return f"published to {current.status}"

    # ── System identities ─────────────────────────────────────────────

    @staticmethod
    def _ensure_system_user(username: str, group_name: str) -> User:
        """Idempotently ensure a system user in the given governance group."""
        user, _ = User.objects.get_or_create(
            username=username, defaults={"is_active": True},
        )
        group, _ = Group.objects.get_or_create(name=group_name)
        if not ScopedRole.objects.filter(
            user=user, group=group, is_active=True,
        ).exists():
            ScopedRole.objects.create(user=user, group=group, is_active=True)
        # Bust any per-request capability cache so the new role is seen.
        if hasattr(user, "_cached_capabilities"):
            del user._cached_capabilities
        return user
