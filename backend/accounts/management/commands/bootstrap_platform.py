"""
accounts/management/commands/bootstrap_platform.py

Idempotent first-run / upgrade bootstrap for Carbon Data Trust Platform.

Creates the foundational CBAC (Capability-Based Access Control) scaffolding:
  1. Django Groups        — from constants.py + GROUP_CAPABILITIES registry
  2. GroupMetadata        — category, description, protection flags
  3. PlatformAppConfig    — per-app enable/disable + ordering
  4. Superuser assignment — all existing superusers → admins_group

Safe to run on every deploy — all operations are INSERT-OR-UPDATE.
Called by entrypoint.sh after migrate (before gunicorn).
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User
from accounts.constants import (
    ADMIN_GROUP, ADMINS_GROUP, DATAOWNERS_GROUP, ANALYSTS_GROUP,
    VIEWERS_GROUP, AUDITORS_GROUP, CARBON_DATA_OWNERS_GROUP,
    CARBON_ANALYSTS_GROUP, CARBON_LEAD_GROUP, CATALOG_LEAD_GROUP,
    MDM_LEAD_GROUP, DQ_LEAD_GROUP, PROTECTED_GROUPS,
    DOMAIN_LEAD_GROUPS,
)
from accounts.models import GroupMetadata, PlatformAppConfig

# ── Group definitions ────────────────────────────────────────────────────────
# name → (category, description, is_protected, is_scoped)
GROUP_DEFS = {
    # ── Platform ──
    ADMIN_GROUP: (
        "platform",
        "Built-in Django admin group — full platform administration (wildcard CBAC)",
        True, False,
    ),
    ADMINS_GROUP: (
        "platform",
        "Platform administrators — manage users, groups, org units, access control",
        True, False,
    ),

    # ── Domain Leads (org-scoped app administrators) ──
    CARBON_LEAD_GROUP: (
        "app",
        "Carbon domain lead — manage emission factors, rules, periods, verify data within org scope",
        True, True,
    ),
    CATALOG_LEAD_GROUP: (
        "app",
        "Catalog domain lead — manage data products, metadata, governance policies within org scope",
        True, True,
    ),
    MDM_LEAD_GROUP: (
        "app",
        "MDM domain lead — manage master data entities and reference sets within org scope",
        True, True,
    ),
    DQ_LEAD_GROUP: (
        "app",
        "DQ domain lead — manage data quality rules and monitor DQ within org scope",
        True, True,
    ),

    # ── Data roles ──
    DATAOWNERS_GROUP: (
        "app",
        "Data owners — enter and manage emission data for assigned org units",
        False, True,
    ),
    CARBON_DATA_OWNERS_GROUP: (
        "app",
        "Carbon data owners — enter, calculate, and verify carbon data for assigned org units",
        False, True,
    ),

    # ── Analyst roles ──
    ANALYSTS_GROUP: (
        "app",
        "Analysts — cross-org read access, generate reports, view analytics",
        False, False,
    ),
    CARBON_ANALYSTS_GROUP: (
        "app",
        "Carbon analysts — cross-org emissions visibility, reporting, trend analysis",
        False, False,
    ),

    # ── Viewer / Auditor ──
    VIEWERS_GROUP: (
        "app",
        "Viewers — org-scoped read-only access to dashboards and data",
        False, True,
    ),
    AUDITORS_GROUP: (
        "app",
        "Auditors — org-scoped read access with governance audit trail visibility",
        False, True,
    ),
}

# ── App registry (mirrors frontend manifests) ─────────────────────────────────
APP_DEFS = [
    {
        "app_id": "carbon",
        "is_enabled": True,
        "display_order": 1,
    },
    {
        "app_id": "stub",
        "is_enabled": False,  # isolation proof — disabled by default
        "display_order": 99,
    },
    {
        "app_id": "catalog",
        "is_enabled": True,
        "display_order": 2,
    },
    {
        "app_id": "mdm",
        "is_enabled": True,
        "display_order": 3,
    },
    {
        "app_id": "dq",
        "is_enabled": True,
        "display_order": 4,
    },
    {
        "app_id": "connections",
        "is_enabled": True,
        "display_order": 5,
    },
    {
        "app_id": "importexport",
        "is_enabled": True,
        "display_order": 6,
    },
    {
        "app_id": "dataschema",
        "is_enabled": True,
        "display_order": 7,
    },
]


class Command(BaseCommand):
    help = "Idempotent platform bootstrap — create groups, app configs, assign superusers."

    def handle(self, *args, **options):
        self._bootstrap_groups()
        self._bootstrap_apps()
        self._assign_superusers()

        self.stdout.write(self.style.SUCCESS(
            "✓ Platform bootstrap complete — groups, apps, superuser assignment ready."
        ))

    # ── Groups + Metadata ────────────────────────────────────────────────────

    def _bootstrap_groups(self):
        created = 0
        updated = 0

        for group_name, (category, description, is_protected, is_scoped) in GROUP_DEFS.items():
            group, was_created = Group.objects.get_or_create(name=group_name)

            meta, _ = GroupMetadata.objects.update_or_create(
                group=group,
                defaults={
                    "description": description,
                    "category": category,
                    "app_id": self._app_id_for_group(group_name),
                    "manifest_key": group_name,
                    "is_scoped": is_scoped,
                    "is_protected": is_protected,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            f"  Groups: {created} created, {updated} up-to-date "
            f"({len(GROUP_DEFS)} total)"
        )

    def _app_id_for_group(self, group_name: str) -> str:
        """Derive app_id from group name: carbon_lead → carbon, catalog_lead → catalog."""
        for prefix in ("carbon", "catalog", "mdm", "dq", "connections", "importexport", "dataschema"):
            if group_name.startswith(prefix):
                return prefix
        if group_name in (ADMIN_GROUP, ADMINS_GROUP):
            return "platform"
        # Generic data/analyst/viewer/auditor groups → carbon as default
        if "_" in group_name:
            return group_name.split("_")[0]
        return "platform"

    # ── Platform Apps ────────────────────────────────────────────────────────

    def _bootstrap_apps(self):
        created = 0
        updated = 0

        for app_def in APP_DEFS:
            _, was_created = PlatformAppConfig.objects.update_or_create(
                app_id=app_def["app_id"],
                defaults={
                    "is_enabled": app_def["is_enabled"],
                    "display_order": app_def["display_order"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            f"  Apps:   {created} created, {updated} up-to-date "
            f"({len(APP_DEFS)} total)"
        )

    # ── Superuser → admins_group ─────────────────────────────────────────────

    def _assign_superusers(self):
        assigned = 0
        admins_group = Group.objects.get(name=ADMINS_GROUP)

        for user in User.objects.filter(is_superuser=True):
            if not user.groups.filter(pk=admins_group.pk).exists():
                user.groups.add(admins_group)
                assigned += 1
                self.stdout.write(f"  + Superuser '{user.username}' → {ADMINS_GROUP}")

        if assigned == 0:
            self.stdout.write("  Superusers: already in admins_group (skip)")
        else:
            self.stdout.write(f"  Superusers: {assigned} assigned to {ADMINS_GROUP}")
