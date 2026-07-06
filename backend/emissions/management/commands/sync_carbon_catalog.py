# emissions/management/commands/sync_carbon_catalog.py
# Wires the Carbon (emissions) app onto the Data Trust core. Additive + idempotent.
# NOTE: emissions may import core apps; core apps must never import emissions.
from django.core.management.base import BaseCommand

from catalog.models import DataDomain, AssetProfile
from catalog.services import ensure_asset_profiles
from mdm.models import ReferenceSet, ReferenceValue
from dq.services import profile_table
from dataschema.models import DataTable
from emissions.models import EmissionFactor


class Command(BaseCommand):
    help = ("Wire Carbon onto the Data Trust core: Emissions domain, governed "
            "reference data (scopes/categories), catalog classification, optional DQ profiling. "
            "Additive and idempotent.")

    def add_arguments(self, parser):
        parser.add_argument('--profile', action='store_true',
                            help='Also run DQ profiling on all platform tables.')

    def handle(self, *args, **options):
        # 1. Emissions domain
        domain, _ = DataDomain.objects.get_or_create(
            slug='emissions',
            defaults={'name': 'Emissions', 'description': 'Carbon / GHG emissions domain'},
        )
        self.stdout.write(f"Domain: {domain.name} (id={domain.id})")

        # 2. Governed reference data from the emissions model choices
        scopes, _ = ReferenceSet.objects.get_or_create(
            slug='emission-scopes',
            defaults={'name': 'Emission Scopes', 'description': 'GHG Protocol scopes', 'domain': domain},
        )
        for code, label in EmissionFactor.SCOPE_CHOICES:
            ReferenceValue.objects.get_or_create(
                reference_set=scopes, code=f'scope_{code}',
                defaults={'label': label, 'sort_order': int(code)},
            )
        categories, _ = ReferenceSet.objects.get_or_create(
            slug='emission-categories',
            defaults={'name': 'Emission Categories', 'domain': domain},
        )
        for i, (code, label) in enumerate(EmissionFactor.CATEGORY_CHOICES):
            ReferenceValue.objects.get_or_create(
                reference_set=categories, code=code,
                defaults={'label': label, 'sort_order': i},
            )
        self.stdout.write(
            f"Reference sets: emission-scopes={scopes.values.count()} "
            f"emission-categories={categories.values.count()}"
        )

        # 3. Classify platform tables into the Emissions domain (via catalog AssetProfile)
        ensure_asset_profiles()
        tables = list(DataTable.objects.all())
        tagged = 0
        for t in tables:
            ap, _ = AssetProfile.objects.get_or_create(data_table=t)
            if ap.domain_id != domain.id:
                ap.domain = domain
                ap.save(update_fields=['domain', 'updated_at'])
                tagged += 1
        self.stdout.write(f"Tables classified into Emissions domain: {tagged} changed / {len(tables)} total")

        # 4. Optional profiling
        if options['profile']:
            for t in tables:
                profile_table(t.id)
            self.stdout.write(f"Profiled {len(tables)} tables")

        self.stdout.write(self.style.SUCCESS("Carbon <-> Data Trust core sync complete"))
