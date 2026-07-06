# core/management/commands/seed_aastmt_org.py
# Seeds a minimal realistic AASTMT org slice + Transportation "Gas Bills" scenario.
# Additive + idempotent. Safe to re-run.

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.text import slugify

from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField
from accounts.models import ScopedRole

User = get_user_model()


def _ou(name, org_type, parent=None, code=''):
    slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
    obj, _ = OrgUnit.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'org_type': org_type, 'parent': parent, 'code': code, 'is_active': True},
    )
    return obj


class Command(BaseCommand):
    help = "Seed a minimal AASTMT org slice + Transportation Gas Bills scenario (idempotent)."

    def handle(self, *args, **options):
        # --- Org tree (campus + departments, not colleges) ---
        aast = OrgUnit.objects.filter(slug='aast').first() or _ou('AAST', 'university', code='AAST')
        abuqir = _ou('Abu Qir Campus', 'campus', parent=aast, code='ABUQIR')
        transport = _ou('Transportation / Fleet', 'department', parent=abuqir, code='TRANS')
        facilities = _ou('Facilities & Utilities', 'department', parent=abuqir, code='FAC')
        procurement = _ou('Procurement & Finance', 'department', parent=abuqir, code='PROC')
        self.stdout.write(
            f"Org tree ready (Abu Qir campus id={abuqir.id}, transport id={transport.id}, facilities id={facilities.id})"
        )

        # --- Transportation module + Gas Bills table ---
        tmod, _ = Module.objects.get_or_create(
            name='Transportation - Fleet Fuel', defaults={'scope': 1, 'org_unit': transport}
        )
        if tmod.org_unit_id != transport.id:
            tmod.org_unit = transport
            tmod.save(update_fields=['org_unit'])

        gtbl, _ = DataTable.objects.get_or_create(
            module=tmod, name='gas_bills',
            defaults={'title': 'Gas Bills', 'description': 'Fleet fuel / gas bills'},
        )
        for name, label, ftype, required, order in [
            ('bill_date', 'Bill Date', 'date', True, 1),
            ('volume_m3', 'Volume (m3)', 'number', True, 2),
            ('amount_egp', 'Amount (EGP)', 'number', True, 3),
            ('supplier', 'Supplier', 'string', False, 4),
            ('invoice_file', 'Invoice File', 'file', False, 5),
        ]:
            DataField.objects.get_or_create(
                data_table=gtbl, name=name,
                defaults={'label': label, 'type': ftype, 'required': required, 'order': order},
            )

        # --- Isolation fixture: a facilities module + table (different department) ---
        emod, _ = Module.objects.get_or_create(
            name='Engineering - Lab Electricity', defaults={'scope': 2, 'org_unit': facilities}
        )
        if emod.org_unit_id != facilities.id:
            emod.org_unit = facilities
            emod.save(update_fields=['org_unit'])
        DataTable.objects.get_or_create(
            module=emod, name='lab_electricity',
            defaults={'title': 'Lab Electricity', 'description': 'Facilities lab electricity'},
        )

        # --- Department users + RBAC assignments ---
        dataowner_group, _ = Group.objects.get_or_create(name='dataowners_group')
        admin_group, _ = Group.objects.get_or_create(name='admins_group')

        for username, password, org_unit, label in [
            ('transport.officer', 'Transport_123', transport, 'Transportation / Fleet'),
            ('facilities.officer', 'Facilities_123', facilities, 'Facilities & Utilities'),
        ]:
            user, _ = User.objects.get_or_create(username=username, defaults={'is_active': True})
            user.set_password(password)
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.save()
            ScopedRole.objects.get_or_create(
                user=user, group=dataowner_group, org_unit=org_unit, module=None,
                defaults={'is_active': True}
            )
            self.stdout.write(f"User {username} created with dataowner role on {label}")

        # Give ahmed a global admin role for the acceptance tests
        ahmed = User.objects.filter(username='ahmed').first()
        if ahmed:
            ahmed.set_password('AdminPa_132')
            ahmed.is_active = True
            ahmed.is_staff = True
            ahmed.is_superuser = True
            ahmed.save()
            ScopedRole.objects.get_or_create(
                user=ahmed, group=admin_group, org_unit=None, module=None, defaults={'is_active': True}
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded. transport.officer / Transport_123 scoped to '{transport.name}'. "
            f"Transportation module id={tmod.id}, gas_bills table id={gtbl.id}; "
            f"Engineering module id={emod.id}."
        ))
