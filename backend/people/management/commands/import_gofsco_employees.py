# people/management/commands/import_gofsco_employees.py
#
# Import the real GOFSCO employee list (August 2026 ERP export) into the People
# app. Source: raw/GOFSCO app/20260905/Updated Employee List - August 2026.xlsx
#
# Excel columns → model mapping:
#   Code        → Employee.employee_no (raw code, e.g. "1399")
#   FullNameEn  → Employee.full_name (+ split into name_en_given/name_en_family)
#   Job Title   → Position.title (one Position per distinct title)
#   Cost Center → OrgUnit (cost_center type under the GOFSCO company root)
#   GOFSCO Email→ (no Employee field — captured in the extraction JSON only)
#   IP Extension→ (no Employee field — captured in the extraction JSON only)
#
# Inference (no salary/nationality/civil_id/hire-date in the export):
#   - Cost centers prefixed "Kuwaitization - " ⇒ kuwaitization=True, KWT
#   - basic_salary defaults to 0.000
#   - join_date left NULL (the export carries no hire date — we do NOT fabricate)
#   - civil_id / date_of_birth / gender left blank (pending enrichment)
#
# Usage:
#   manage.py import_gofsco_employees                  # extract + append
#   manage.py import_gofsco_employees --dry-run        # extract + report only
#   manage.py import_gofsco_employees --path <xlsx>    # override source
#
# Idempotent: org units / positions / employees are upserted by natural key.

import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

# Repo root = settings.BASE_DIR.parent (BASE_DIR is backend/). In dev the source
# lives under raw/ at the repo root; on the server, override with --path.
REPO_ROOT = settings.BASE_DIR.parent
DEFAULT_PATH = (
    REPO_ROOT / "raw/GOFSCO app/20260905/Updated Employee List - August 2026.xlsx"
)

KW_PREFIX = "Kuwaitization - "

EMAIL_NA = {"#N/A", "", "N/A", "None"}


def _clean(v):
    return "" if v is None else str(v).strip()


def read_employees(path):
    """Parse the ERP export into a list of normalised employee dicts."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    employees = []
    for r in rows[1:]:
        if not r or _clean(r[0]) == "":
            continue
        email = _clean(r[4])
        if email in EMAIL_NA:
            email = ""
        ip_ext = _clean(r[5])
        if ip_ext in EMAIL_NA:
            ip_ext = ""
        employees.append({
            "code": _clean(r[0]),
            "full_name": _clean(r[1]),
            "job_title": _clean(r[2]),
            "cost_center": _clean(r[3]),
            "email": email,
            "ip_extension": ip_ext,
        })
    return employees


def split_name(full_name):
    """Rough split into given/family: first token = given, remainder = family."""
    parts = full_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def normalize_cost_center(raw):
    """Return (department, kuwaitization) with the kuwaitization prefix stripped."""
    if raw.startswith(KW_PREFIX):
        return raw[len(KW_PREFIX):], True
    return raw, False


def job_family_for(title):
    """Very light job-title → job_family heuristic (best-effort)."""
    t = title.lower()
    if any(k in t for k in ("engineer", "technician", "operator", "mechanic",
                            "electrician", "welder", "driller", "tool pusher",
                            "supervisor", "foreman", "rig")):
        return "operations"
    if any(k in t for k in ("driver", "cleaner", "helper", "roustabout", "floorman")):
        return "operations"
    if any(k in t for k in ("account", "finance", "payroll", "audit")):
        return "finance"
    if any(k in t for k in ("hr", "human resource", "admin", "secretary",
                            "reception", "government relation", "residency")):
        return "admin"
    if any(k in t for k in ("safety", "hse", "medic", "nurse", "security")):
        return "hse"
    return "operations"


class Command(BaseCommand):
    help = 'Import the real GOFSCO employee list (August 2026 xlsx) into People'

    def add_arguments(self, parser):
        parser.add_argument('--path', default=DEFAULT_PATH,
                            help='Path to the employee-list xlsx')
        parser.add_argument('--dry-run', action='store_true',
                            help='Extract + report only; do not write to the DB')

    def handle(self, *args, **options):
        from mdm.models import OrgUnit
        from people.models import Employee, Position

        path = Path(options['path'])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Source not found: {path}'))
            return

        employees = read_employees(path)
        self.stdout.write(self.style.SUCCESS(
            f'Extracted {len(employees)} employee rows from {path}'
        ))

        # ── Write extraction JSON (provenance, mirrors extract_gofsco_raw.py) ──
        # Extracted artifacts live next to the source file, wherever it is,
        # so the command works on the server without hardcoded paths.
        out_dir = path.parent / '_extracted'
        out_dir.mkdir(parents=True, exist_ok=True)
        cost_centers = sorted({e['cost_center'] for e in employees})
        job_titles = sorted({e['job_title'] for e in employees})
        (out_dir / 'employees.json').write_text(
            json.dumps(employees, indent=2, ensure_ascii=False), encoding='utf-8')
        (out_dir / '_employee_list_summary.json').write_text(
            json.dumps({
                'source': str(path),
                'employees': len(employees),
                'cost_centers': cost_centers,
                'job_titles': job_titles,
            }, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(f'Extraction JSON → {out_dir}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — {len(employees)} employees, '
                f'{len(cost_centers)} cost centers, {len(job_titles)} job titles'
            ))
            return

        # ── Populate ───────────────────────────────────────────────────────
        with transaction.atomic():
            root, _ = OrgUnit.objects.get_or_create(
                code='GOFSCO',
                defaults={
                    'name': 'GOFSCO — Gas & Oil Field Services Company',
                    'slug': 'gofsco',
                    'org_type': 'company',
                    'is_active': True,
                },
            )

            # Org units (cost centers) — slug is globally unique, so disambiguate
            # colliding slugs (e.g. "Surface Well Testing - International" vs
            # the Kuwaitization-stripped "Surface Well Testing International").
            used_slugs = set(
                OrgUnit.objects.exclude(pk=root.pk).values_list('slug', flat=True)
            )
            dept_ous = {}
            for cc in cost_centers:
                dept, _kuwait = normalize_cost_center(cc)
                if dept in dept_ous:
                    continue
                base = slugify(dept) or f'cc-{len(dept_ous) + 1}'
                slug = base
                n = 2
                while slug in used_slugs:
                    slug = f'{base}-{n}'
                    n += 1
                used_slugs.add(slug)
                ou, _ = OrgUnit.objects.get_or_create(
                    parent=root, name=dept,
                    defaults={
                        'slug': slug,
                        'code': base[:50],
                        'org_type': 'cost_center',
                        'is_active': True,
                    },
                )
                dept_ous[dept] = ou

            # Positions (one per distinct job title)
            pos_by_title = {}
            for i, title in enumerate(job_titles, 1):
                pos, _ = Position.objects.get_or_create(
                    org_unit=root, title=title,
                    defaults={
                        'code': f'JOB-{slugify(title)[:44].upper() or i}',
                        'status': 'filled',
                        'fte': Decimal('1.0'),
                        'job_family_code': job_family_for(title),
                    },
                )
                pos_by_title[title] = pos

            created = 0
            updated = 0
            for e in employees:
                dept, kuwait = normalize_cost_center(e['cost_center'])
                ou = dept_ous[dept]
                pos = pos_by_title[e['job_title']]
                given, family = split_name(e['full_name'])

                emp, was_created = Employee.objects.update_or_create(
                    employee_no=e['code'],
                    defaults={
                        'full_name': e['full_name'],
                        'name_en_given': given,
                        'name_en_family': family,
                        'org_unit': ou,
                        'position': pos,
                        'basic_salary': Decimal('0.000'),
                        'join_date': None,
                        'employment_type_code': 'full-time',
                        'contract_type_code': 'indeterminate',
                        'kuwaitization': kuwait,
                        'nationality_code': 'KWT' if kuwait else '',
                        'nationality': 'Kuwaiti' if kuwait else '',
                        'civil_id': '',
                        'gender': '',
                        'rotation': '',
                        'is_active': True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created} created, {updated} updated '
            f'({len(cost_centers)} cost centers, {len(job_titles)} positions)'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Org units now: {OrgUnit.objects.count()} | '
            f'Positions now: {Position.objects.count()} | '
            f'Employees now: {Employee.objects.count()}'
        ))
