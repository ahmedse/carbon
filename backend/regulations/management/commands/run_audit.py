# regulations/management/commands/run_audit.py
# Usage: manage.py run_audit --program <slug-or-id> [--date YYYY-MM-DD] [--dry-run]
from datetime import date
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Execute an AuditProgram and print findings."

    def add_arguments(self, parser):
        parser.add_argument('--program', required=True,
            help='AuditProgram name or ID')
        parser.add_argument('--date', default=None,
            help='Assessment date YYYY-MM-DD (default: today)')
        parser.add_argument('--dry-run', action='store_true',
            help='Show what would run without persisting findings')

    def handle(self, *args, **options):
        from regulations.models import AuditProgram, AuditRun
        from regulations.engine import AuditEngine

        prog_key = options['program']
        try:
            prog = AuditProgram.objects.get(pk=int(prog_key))
        except (ValueError, AuditProgram.DoesNotExist):
            prog = AuditProgram.objects.filter(name__icontains=prog_key).first()
        if prog is None:
            self.stderr.write(self.style.ERROR(f"AuditProgram not found: {prog_key!r}"))
            return

        run_date = date.fromisoformat(options['date']) if options['date'] else date.today()

        self.stdout.write(f"Program:  {prog.name}")
        self.stdout.write(f"Date:     {run_date}")
        self.stdout.write(f"Obligations: {prog.obligations.filter(is_active=True).count()}")
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN — no findings persisted"))
            return

        run = AuditRun.objects.create(program=prog, run_date=run_date)
        engine = AuditEngine()
        engine.execute(run)
        run.refresh_from_db()

        s = run.summary
        self.stdout.write(self.style.SUCCESS(
            f"\nComplete: {s.get('total',0)} findings — "
            f"{s.get('compliant',0)} compliant, "
            f"{s.get('non_compliant',0)} non-compliant, "
            f"{s.get('partial',0)} partial, "
            f"{s.get('error',0)} errors"
        ))

        findings = run.findings.select_related('obligation').order_by('result', 'scope_label')
        for f in findings:
            icon = {'compliant': '✓', 'non_compliant': '✗', 'partial': '~', 'na': '-', 'error': '!'}.get(f.result, '?')
            cv = f.computed_value
            detail = ''
            if 'actual' in cv and 'expected' in cv:
                detail = f"  actual={cv['actual']} / expected={cv['expected']}"
                if 'fill_rate_pct' in cv:
                    detail += f"  ({cv['fill_rate_pct']}%)"
            self.stdout.write(f"  {icon} [{f.severity:8s}] {f.obligation.code:40s}  {f.scope_label}{detail}")
