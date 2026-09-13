# regulations/management/commands/seed_regulations.py
# Seeds the authoritative regulation schemes, obligations, and audit programs.
# Idempotent. Covers: KOC Kuwaitization, Kuwait Labour Law (leave entitlement).
from datetime import date
from django.core.management.base import BaseCommand


# ── Scheme definitions ────────────────────────────────────────────────────────
SCHEMES = [
    {
        'slug': 'koc-kuwaitization',
        'name': 'KOC Kuwaitization Requirements',
        'authority': 'Kuwait Oil Company (KOC)',
        'version': 'Rev. V.11 April 2017',
        'effective_from': date(2017, 4, 1),
        'description': (
            'KOC contractual obligation requiring contractors to employ Kuwaiti nationals '
            'in specified headcount quotas per service contract, as detailed in Appendix 4 '
            '(Kuwaitization) of each KOC contract specification.'
        ),
    },
    {
        'slug': 'kll-2010',
        'name': 'Kuwait Labour Law No. 6/2010',
        'authority': 'Kuwait Ministry of Social Affairs and Labour',
        'version': '2010 + Ministerial Order 176/2012',
        'effective_from': date(2010, 1, 1),
        'description': (
            'Kuwait Labour Law governing employment terms, leave entitlements, EOSI, '
            'overtime, and working conditions for private sector employees.'
        ),
    },
]

# ── Obligation definitions ────────────────────────────────────────────────────
OBLIGATIONS = [
    {
        'scheme_slug': 'koc-kuwaitization',
        'code': 'KOC-KW-001',
        'name': 'Per-Contract Kuwaitization Headcount Quota',
        'description': (
            'The contractor must maintain the KOC-specified number of Kuwaiti nationals '
            'deployed per service contract at all times. Vacancies constitute a contractual breach.'
        ),
        'scope_type': 'koc_contract',
        'formula_type': 'koc_kuwaitization_quota',
        'formula_params': {},
        'severity': 'major',
        'citation': 'KOC Contract Appendix 4 — KUWAITISATION, Section III: Requirements',
    },
    {
        'scheme_slug': 'kll-2010',
        'code': 'KLL-LEAVE-001',
        'name': 'Annual Leave Entitlement Coverage',
        'description': (
            'Every active employee must have a leave entitlement record for the assessment year '
            'covering at minimum annual and sick leave, as required by KLL Art. 70.'
        ),
        'scope_type': 'company',
        'formula_type': 'kll_leave_entitlement',
        'formula_params': {},
        'severity': 'major',
        'citation': 'Kuwait Labour Law No. 6/2010, Arts. 70–75',
    },
]

# ── Audit program ─────────────────────────────────────────────────────────────
PROGRAMS = [
    {
        'name': 'GOFSCO — KOC & Labour Compliance',
        'description': (
            'Quarterly compliance audit covering KOC Kuwaitization headcount obligations '
            'and Kuwait Labour Law leave entitlement requirements.'
        ),
        'obligation_codes': ['KOC-KW-001', 'KLL-LEAVE-001'],
    },
]


class Command(BaseCommand):
    help = 'Seed regulation schemes, obligations, and audit programs (idempotent).'

    def handle(self, *args, **options):
        from regulations.models import RegulationScheme, Obligation, AuditProgram

        # 1. Schemes
        for s in SCHEMES:
            obj, created = RegulationScheme.objects.update_or_create(
                slug=s['slug'],
                defaults={k: v for k, v in s.items() if k != 'slug'},
            )
            action = 'created' if created else 'updated'
            self.stdout.write(f"  scheme {action}: {obj.name}")

        # 2. Obligations
        obligation_map = {}
        for o in OBLIGATIONS:
            scheme = RegulationScheme.objects.get(slug=o['scheme_slug'])
            obj, created = Obligation.objects.update_or_create(
                scheme=scheme,
                code=o['code'],
                defaults={k: v for k, v in o.items() if k not in ('scheme_slug', 'code')},
            )
            obligation_map[o['code']] = obj
            action = 'created' if created else 'updated'
            self.stdout.write(f"  obligation {action}: {obj}")

        # 3. Programs
        for p in PROGRAMS:
            prog, created = AuditProgram.objects.update_or_create(
                name=p['name'],
                defaults={'description': p['description'], 'is_active': True},
            )
            for code in p['obligation_codes']:
                ob = obligation_map.get(code)
                if ob:
                    prog.obligations.add(ob)
            action = 'created' if created else 'updated'
            self.stdout.write(self.style.SUCCESS(
                f"  program {action}: {prog.name} ({prog.obligations.count()} obligations)"
            ))

        self.stdout.write(self.style.SUCCESS('\n✓ Regulations seeded.'))
