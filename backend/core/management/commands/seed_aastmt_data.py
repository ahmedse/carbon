"""
core/management/commands/seed_aastmt_data.py

Seeds real AASTMT Abu Qir campus emission data from the Smart AASTMT Carbon
Emmission spreadsheet (FY 2023/2024 + partial 2024/2025).

Idempotent: safe to re-run. Cleans placeholder/demo schemas first.

Sources:
  - Electricity (Scope 2, Facility-level) — buildings 401 + 2401, monthly kWh
  - Water (Scope 3, Facility-level) — buildings 401 + 2401, monthly m³
  - Chilled Water (Scope 2, Facility-level) — meters 2401-1 + 2401-2, monthly TR
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow


# ── Raw data from spreadsheet (month, bldg_401, bldg_2401) ──────────────────

ELECTRICITY_KWH = [
    # (year, month, bldg_401, bldg_2401)
    (2023,  1, 115382, 120610), (2023,  2, 103340, 101343),
    (2023,  3, 105927,  93214), (2023,  4, 117759, 108461),
    (2023,  5, 110347,  99877), (2023,  6, 113346, 100961),
    (2023,  7, 135858, 148521), (2023,  8, 112649, 120370),
    (2023,  9, 120814, 127254), (2023, 10, 126386, 137655),
    (2023, 11, 112837, 120993), (2023, 12, 117790, 139373),
    (2024,  1, 111359, 121330), (2024,  2,  97263, 102101),
    (2024,  3,  95113,  99299), (2024,  4,  87218,  96150),
    (2024,  5,  77746,  82610), (2024,  6, 109777, 103721),
    (2024,  7, 155548, 150839), (2024,  8, 115568, 109794),
    (2024,  9, 137560, 128355), (2024, 12, 125459, 127958),
    (2025,  1, 102491, 101366), (2025,  2,  98601, 100569),
    (2025,  3,  96374,  96538), (2025,  4,  83200,  85765),
]

WATER_M3 = [
    # (year, month, bldg_401, bldg_2401)
    (2023,  1, 596, 777), (2023,  2, 597, 778), (2023,  3, 605, 675),
    (2023,  4, 605, 675), (2023,  5, 314, 393), (2023,  6, 314, 393),
    (2023,  7, 390, 568), (2023,  8, 390, 569), (2023,  9, 388, 592),
    (2023, 10, 388, 592), (2023, 11, 570, 738), (2023, 12, 570, 738),
    (2024,  1, 370, 480), (2024,  2, 370, 480), (2024,  3, 369, 453),
    (2024,  4, 370, 454), (2024,  5, 403, 422), (2024,  6, 404, 422),
]

CHILLED_WATER_TR = [
    # (year, month, meter_2401_1, meter_2401_2)
    (2023,  1, 12167.70,   8090.19), (2023,  2, 10705.31,  4941.63),
    (2023,  3, 48832.01,  42261.93), (2023,  4, 44631.38,  38108.50),
    (2023,  5, 92111.90, 103376.23), (2023,  6, 108327.54, 132851.61),
    (2023,  7, 123137.37, 142293.41), (2023,  8, 145725.18, 149811.78),
    (2023,  9, 111631.06, 113992.83), (2023, 10, 107347.68, 114852.12),
    (2023, 11,  76780.30,  75870.68), (2023, 12,  37742.27,  38258.07),
    (2024,  1,  29829.23,  28559.06), (2024,  2,  28492.80,  28211.59),
    (2024,  3,  32719.03,  36263.67), (2024,  4,  55375.08,  61304.53),
    (2024,  5,  88462.33, 100468.80), (2024,  6, 121842.74, 113121.59),
    (2024,  7, 153098.25, 160167.35),
    (2025,  2,   8385.34,   7787.64),
]


class Command(BaseCommand):
    help = "Seed real AASTMT Abu Qir emission data. Cleans demo/placeholder schemas first."

    def handle(self, *args, **options):
        # ── 1. Clean placeholder/demo DataTables & Modules ─────────────────
        self.stdout.write("Cleaning placeholder schemas...")
        demo_names = ['MDM Module', 'Operations', 'gas_bills', 'Engineering - Lab Electricity',
                      'Transportation - Fleet Fuel']
        # Delete DataRows + DataTables in demo modules
        placeholder_modules = Module.objects.filter(name__in=demo_names)
        for m in placeholder_modules:
            tbl_count = DataTable.objects.filter(module=m).count()
            DataRow.objects.filter(data_table__module=m).delete()
            DataTable.objects.filter(module=m).delete()
            self.stdout.write(f"  Removed module '{m.name}' ({tbl_count} tables)")
        placeholder_modules.delete()

        # Also remove any orphan demo tables by name
        for t in DataTable.objects.filter(name__in=['gas_bills', 'lab_electricity', 'dq_test_table']):
            DataRow.objects.filter(data_table=t).delete()
            t.delete()
            self.stdout.write(f"  Removed orphan table '{t.name}'")

        # ── 2. Ensure Facilities & Utilities org unit exists ────────────────
        abuqir = OrgUnit.objects.filter(slug='aast-abu-qir-campus').first()
        if not abuqir:
            self.stdout.write(self.style.ERROR("Abu Qir Campus org unit not found. Run seed_aastmt_org first."))
            return
        fac = OrgUnit.objects.filter(slug__contains='facilities').first()
        if not fac:
            self.stdout.write(self.style.ERROR("Facilities org unit not found. Run seed_aastmt_org first."))
            return
        self.stdout.write(f"Using org unit: {fac.full_path()}")

        # ── 3. Create modules + tables ──────────────────────────────────────
        # Electricity – Scope 2
        elec_mod, _ = Module.objects.get_or_create(
            name='Facilities - Electricity', defaults={'scope': 2, 'org_unit': fac}
        )
        elec_tbl, _ = DataTable.objects.get_or_create(
            module=elec_mod, name='monthly_electricity',
            defaults={'title': 'Monthly Electricity (kWh)', 'description': 'Abu Qir campus monthly electricity consumption per building.'}
        )
        self._ensure_fields(elec_tbl, [
            ('month',          'Month',              'date',   True,  1),
            ('building_401_kwh', 'Building 401 (kWh)', 'number', True,  2),
            ('building_2401_kwh','Building 2401 (kWh)','number', True,  3),
            ('total_kwh',       'Total (kWh)',         'number', False, 4),
        ])

        # Water – Scope 3
        water_mod, _ = Module.objects.get_or_create(
            name='Facilities - Water', defaults={'scope': 3, 'org_unit': fac}
        )
        water_tbl, _ = DataTable.objects.get_or_create(
            module=water_mod, name='monthly_water',
            defaults={'title': 'Monthly Water (m³)', 'description': 'Abu Qir campus monthly water consumption per building.'}
        )
        self._ensure_fields(water_tbl, [
            ('month',          'Month',          'date',   True,  1),
            ('building_401_m3', 'Building 401 (m³)', 'number', True,  2),
            ('building_2401_m3','Building 2401 (m³)','number', True,  3),
            ('total_m3',        'Total (m³)',      'number', False, 4),
        ])

        # Chilled Water – Scope 2
        chill_mod, _ = Module.objects.get_or_create(
            name='Facilities - Chilled Water', defaults={'scope': 2, 'org_unit': fac}
        )
        chill_tbl, _ = DataTable.objects.get_or_create(
            module=chill_mod, name='monthly_chilled_water',
            defaults={'title': 'Monthly Chilled Water (TR)', 'description': 'Abu Qir campus chilled water consumption — meters 2401-1 and 2401-2.'}
        )
        self._ensure_fields(chill_tbl, [
            ('month',             'Month',              'date',   True,  1),
            ('meter_2401_1_tr',   'Meter 2401-1 (TR)',  'number', True,  2),
            ('meter_2401_2_tr',   'Meter 2401-2 (TR)',  'number', True,  3),
            ('total_tr',          'Total (TR)',          'number', False, 4),
        ])

        # ── 4. Seed rows (clear old, insert fresh) ──────────────────────────
        DataRow.objects.filter(data_table=elec_tbl).delete()
        DataRow.objects.filter(data_table=water_tbl).delete()
        DataRow.objects.filter(data_table=chill_tbl).delete()

        for year, month, b401, b2401 in ELECTRICITY_KWH:
            DataRow.objects.create(data_table=elec_tbl, values={
                'month': f'{year:04d}-{month:02d}-01',
                'building_401_kwh': b401,
                'building_2401_kwh': b2401,
                'total_kwh': b401 + b2401,
            })
        for year, month, b401, b2401 in WATER_M3:
            DataRow.objects.create(data_table=water_tbl, values={
                'month': f'{year:04d}-{month:02d}-01',
                'building_401_m3': b401,
                'building_2401_m3': b2401,
                'total_m3': b401 + b2401,
            })
        for year, month, m1, m2 in CHILLED_WATER_TR:
            DataRow.objects.create(data_table=chill_tbl, values={
                'month': f'{year:04d}-{month:02d}-01',
                'meter_2401_1_tr': round(m1, 2),
                'meter_2401_2_tr': round(m2, 2),
                'total_tr': round(m1 + m2, 2),
            })

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded:"
            f"\n  Electricity  → {elec_tbl.title}: {len(ELECTRICITY_KWH)} rows (module id={elec_mod.id})"
            f"\n  Water        → {water_tbl.title}: {len(WATER_M3)} rows (module id={water_mod.id})"
            f"\n  Chilled Water→ {chill_tbl.title}: {len(CHILLED_WATER_TR)} rows (module id={chill_mod.id})"
        ))
        self.stdout.write(f"Facilities user 'facilities.officer' can view/edit these tables.")

    def _ensure_fields(self, table, fields):
        """Idempotently create fields on a table."""
        for name, label, ftype, required, order in fields:
            DataField.objects.get_or_create(
                data_table=table, name=name,
                defaults={'label': label, 'type': ftype, 'required': required, 'order': order},
            )
