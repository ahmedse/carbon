# people/management/commands/assign_employee_managers.py
"""Assign Employee.manager (and optionally OrgUnit.manager_employee_id).

GOFSCO import never sets managers — Team inbox stays empty until this runs.

Modes:
  --csv path.csv     rows: employee_no,manager_employee_no
  --org-leads        DEV/QA heuristic: per org unit pick a lead (title rank /
                     existing managers / lowest employee_no with a user) and
                     assign every other active employee in that unit to them.
                     Existing manager FKs are kept unless --force.

Always prefer --csv for production-like data.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mdm.models import OrgUnit
from people.models import Employee

# Higher score → preferred as org lead (title heuristic for --org-leads).
_LEAD_TITLE_SCORE = (
    ("general manager", 100),
    ("country manager", 95),
    ("operations manager", 90),
    ("operation manager", 90),
    ("project director", 85),
    ("director", 80),
    ("manager", 70),
    ("superintendent", 65),
    ("tool pusher", 60),
    ("senior supervisor", 55),
    ("team leader", 50),
    ("senior foreman", 48),
    ("supervisor", 40),
    ("foreman", 38),
    ("coordinator", 35),
)


def _title_score(emp: Employee) -> int:
    title = ""
    if emp.position_id and emp.position:
        title = (emp.position.title or "").lower()
    for needle, score in _LEAD_TITLE_SCORE:
        if needle in title:
            return score
    return 0


def _pick_org_lead(employees: list[Employee]) -> Employee | None:
    """Prefer titled leads, then anyone who already manages someone, then lowest no."""
    if not employees:
        return None
    report_counts: dict[int, int] = {}
    for e in employees:
        if e.manager_id:
            report_counts[e.manager_id] = report_counts.get(e.manager_id, 0) + 1
    ranked = sorted(
        employees,
        key=lambda e: (
            -_title_score(e),
            -report_counts.get(e.id, 0),
            e.employee_no or "",
            e.id,
        ),
    )
    for e in ranked:
        if e.user_id:
            return e
    return ranked[0]


class Command(BaseCommand):
    help = (
        "Assign Employee.manager from CSV or --org-leads heuristic "
        "(GOFSCO import leaves managers null)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default="",
            help="CSV with columns employee_no,manager_employee_no",
        )
        parser.add_argument(
            "--org-leads",
            action="store_true",
            help="Assign unassigned employees to a per-org-unit lead (DEV/QA).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing Employee.manager values.",
        )
        parser.add_argument(
            "--set-org-unit-manager",
            action="store_true",
            help="Also set OrgUnit.manager_employee_id to each unit's lead.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing.",
        )

    def handle(self, *args, **options):
        csv_path = (options.get("csv_path") or "").strip()
        org_leads = bool(options.get("org_leads"))
        force = bool(options.get("force"))
        set_ou = bool(options.get("set_org_unit_manager"))
        dry_run = bool(options.get("dry_run"))

        if bool(csv_path) == org_leads:
            raise CommandError("Pass exactly one of --csv <path> or --org-leads.")

        if csv_path:
            mapping = self._load_csv(csv_path)
            stats = self._apply_mapping(mapping, force=force, dry_run=dry_run)
        else:
            stats = self._apply_org_leads(
                force=force, set_ou=set_ou, dry_run=dry_run,
            )

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}managers: assigned={stats['assigned']} "
                f"skipped_existing={stats['skipped']} "
                f"missing={stats['missing']} "
                f"org_units_updated={stats.get('org_units', 0)}"
            )
        )

    def _load_csv(self, path: str) -> dict[str, str]:
        p = Path(path)
        if not p.is_file():
            raise CommandError(f"CSV not found: {path}")
        mapping: dict[str, str] = {}
        with p.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "employee_no" not in reader.fieldnames:
                raise CommandError(
                    "CSV must include headers employee_no,manager_employee_no"
                )
            for row in reader:
                emp_no = (row.get("employee_no") or "").strip()
                mgr_no = (row.get("manager_employee_no") or "").strip()
                if not emp_no or not mgr_no:
                    continue
                if emp_no == mgr_no:
                    continue
                mapping[emp_no] = mgr_no
        if not mapping:
            raise CommandError("CSV produced no assignments.")
        return mapping

    def _apply_mapping(self, mapping: dict[str, str], *, force: bool, dry_run: bool):
        by_no = {
            e.employee_no: e
            for e in Employee.objects.select_related("manager").all()
        }
        stats = {"assigned": 0, "skipped": 0, "missing": 0, "org_units": 0}
        updates: list[Employee] = []
        for emp_no, mgr_no in mapping.items():
            emp = by_no.get(emp_no)
            mgr = by_no.get(mgr_no)
            if emp is None or mgr is None:
                stats["missing"] += 1
                continue
            if emp.manager_id and not force:
                stats["skipped"] += 1
                continue
            if emp.manager_id == mgr.id:
                stats["skipped"] += 1
                continue
            emp.manager = mgr
            updates.append(emp)
            stats["assigned"] += 1
        if not dry_run and updates:
            with transaction.atomic():
                Employee.objects.bulk_update(updates, ["manager"], batch_size=200)
        return stats

    def _apply_org_leads(self, *, force: bool, set_ou: bool, dry_run: bool):
        stats = {"assigned": 0, "skipped": 0, "missing": 0, "org_units": 0}
        qs = (
            Employee.objects.filter(is_active=True)
            .select_related("position", "manager", "org_unit", "user")
            .order_by("org_unit_id", "employee_no")
        )
        by_ou: dict[int | None, list[Employee]] = {}
        for emp in qs:
            by_ou.setdefault(emp.org_unit_id, []).append(emp)

        updates: list[Employee] = []
        ou_updates: list[OrgUnit] = []

        for ou_id, members in by_ou.items():
            if ou_id is None:
                stats["missing"] += len(members)
                continue
            lead = _pick_org_lead(members)
            if lead is None:
                stats["missing"] += len(members)
                continue
            if set_ou:
                ou = lead.org_unit
                if ou and ou.manager_employee_id != lead.id:
                    ou.manager_employee_id = lead.id
                    ou_updates.append(ou)
                    stats["org_units"] += 1
            for emp in members:
                if emp.id == lead.id:
                    continue
                if emp.manager_id and not force:
                    stats["skipped"] += 1
                    continue
                if emp.manager_id == lead.id:
                    stats["skipped"] += 1
                    continue
                emp.manager = lead
                updates.append(emp)
                stats["assigned"] += 1

        if not dry_run:
            with transaction.atomic():
                if updates:
                    Employee.objects.bulk_update(updates, ["manager"], batch_size=200)
                if ou_updates:
                    OrgUnit.objects.bulk_update(
                        ou_updates, ["manager_employee_id"], batch_size=100,
                    )
        return stats
