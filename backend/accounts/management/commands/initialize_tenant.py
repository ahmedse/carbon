from django.core.management.base import BaseCommand
from accounts.models import Tenant, User

class Command(BaseCommand):
    help = 'Creates an initial tenant and superuser if they do not exist.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default='DevTenant', help='Tenant name')
        parser.add_argument('--username', type=str, default='admin', help='Superuser username')
        parser.add_argument('--password', type=str, default='Admin_132', help='Superuser password')
        parser.add_argument('--email', type=str, default='admin@example.com', help='Superuser email')

    def handle(self, *args, **options):
        tenant_name = options['tenant']
        username = options['username']
        password = options['password']
        email = options['email']

        # 1. Create or get the tenant
        tenant, created = Tenant.objects.get_or_create(name=tenant_name)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created tenant: {tenant_name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Tenant already exists: {tenant_name}"))

        # 2. Create the superuser for this tenant if not exists
        if not User.objects.filter(username=username, tenant=tenant).exists():
            User.objects.create_superuser(username=username, password=password, tenant=tenant, email=email)
            self.stdout.write(self.style.SUCCESS(f"Created superuser: {username} (tenant={tenant_name})"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser already exists: {username} (tenant={tenant_name})"))