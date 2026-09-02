# mdm/management/commands/seed_gofsco_org.py
# Seeds the GOFSCO org tree (Gas and Oil Field Services Company, Kuwait — KOC client).
# Additive + idempotent. Safe to re-run (get_or_create by slug).
# Mirror of core/management/commands/seed_aastmt_org.py.

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from mdm.models import OrgUnit


def _ou(name, org_type, parent=None, code=''):
    slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
    obj, _ = OrgUnit.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'org_type': org_type, 'parent': parent, 'code': code, 'is_active': True},
    )
    return obj


class Command(BaseCommand):
    help = "Seed the GOFSCO org tree (company / base / division / yard / store / section / crew) — idempotent."

    def handle(self, *args, **options):
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
