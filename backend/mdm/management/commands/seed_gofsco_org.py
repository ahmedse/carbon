# mdm/management/commands/seed_gofsco_org.py
# Seeds the GOFSCO org tree (Gas and Oil Field Services Company, Kuwait — KOC client).
# Additive + idempotent. Safe to re-run (get_or_create by slug).
# Mirror of core/management/commands/seed_aastmt_org.py.
# ADR-0028: instance-gated — only GOFSCO/Nibras deployments.

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from mdm.models import OrgUnit
from mdm.services import is_gofsco_org_seed_allowed


def _ou(name, org_type, parent=None, code=''):
    slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
    obj, _ = OrgUnit.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'org_type': org_type, 'parent': parent, 'code': code, 'is_active': True},
    )
    return obj


def _assert_gofsco_instance():
    if is_gofsco_org_seed_allowed():
        return
    brand = getattr(settings, 'DJANGO_BRAND', None)
    instance = getattr(settings, 'INSTANCE_NAME', None)
    raise CommandError(
        "seed_gofsco_org is instance-gated (ADR-0028): run only when "
        "DJANGO_BRAND or DJANGO_INSTANCE_NAME/INSTANCE_NAME is in "
        "{'gofsco', 'nibras'}. "
        f"Current DJANGO_BRAND={brand!r}, INSTANCE_NAME={instance!r}."
    )


class Command(BaseCommand):
    help = (
        "Seed the GOFSCO org tree (company / base / division / yard / store / "
        "section / crew) — idempotent. Allowed only on gofsco/nibras deployments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print the planned root/tree actions without writing.',
        )

    def handle(self, *args, **options):
        _assert_gofsco_instance()
        dry = options.get('dry_run', False)
        if dry:
            existing = OrgUnit.objects.filter(slug='gofsco').first()
            self.stdout.write(
                f"[dry-run] would ensure GOFSCO root "
                f"(exists={bool(existing)}, id={getattr(existing, 'id', None)}) "
                f"+ Ahmadi Base / divisions / crews (idempotent get_or_create)."
            )
            return

        # --- Root company ---
        gofsco = OrgUnit.objects.filter(slug='gofsco').first() or _ou('GOFSCO', 'company', code='GOFSCO')
        # Re-runs: keep the root marker stable (slug 'gofsco') even if it was
        # re-parented or re-typed by hand in between runs.
        if gofsco.org_type != 'company' or gofsco.code != 'GOFSCO' or gofsco.parent_id is not None:
            gofsco.org_type = 'company'
            gofsco.code = 'GOFSCO'
            gofsco.parent = None
            gofsco.save(update_fields=['org_type', 'code', 'parent'])

        # --- Ahmadi Base + divisions ---
        ahmadi = _ou('Ahmadi Base', 'base', parent=gofsco, code='AHM')

        drilling = _ou('Drilling Division', 'division', parent=ahmadi, code='DRL')
        drilling_yard = _ou('Drilling Yard', 'yard', parent=drilling, code='DRL-YD')
        _ou('Drilling Store', 'store', parent=drilling_yard, code='DRL-ST')

        ct = _ou('CT Division', 'division', parent=ahmadi, code='CT')
        ct_yard = _ou('CT Yard', 'yard', parent=ct, code='CT-YD')
        _ou('CT Store', 'store', parent=ct_yard, code='CT-ST')

        pcp = _ou('PCP Division', 'division', parent=ahmadi, code='PCP')
        pcp_yard = _ou('PCP Yard', 'yard', parent=pcp, code='PCP-YD')
        _ou('PCP Store', 'store', parent=pcp_yard, code='PCP-ST')

        # --- Direct sections / store under Ahmadi Base ---
        _ou('Finance & Admin', 'section', parent=ahmadi, code='FIN')
        _ou('HR & Training', 'section', parent=ahmadi, code='HR')
        _ou('Warehouse / Main Store', 'store', parent=ahmadi, code='WHS')

        # --- Operations crews (site-level, under GOFSCO) ---
        crew1 = _ou('Operations Crew 1', 'crew', parent=gofsco, code='CREW-1')
        crew2 = _ou('Operations Crew 2', 'crew', parent=gofsco, code='CREW-2')

        self.stdout.write(self.style.SUCCESS(
            f"GOFSCO org tree ready: root id={gofsco.id}, Ahmadi Base id={ahmadi.id}, "
            f"Drilling Division id={drilling.id}, CT Division id={ct.id}, "
            f"PCP Division id={pcp.id}, Crew 1 id={crew1.id}, Crew 2 id={crew2.id}"
        ))
