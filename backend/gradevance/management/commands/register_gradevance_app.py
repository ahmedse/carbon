from django.core.management.base import BaseCommand

from appregistry.services import AppRegistryService


class Command(BaseCommand):
    help = "Register GradeVance app manifest in AppRegistry (idempotent)."

    def handle(self, *args, **options):
        manifest, created = AppRegistryService.register_manifest(
            slug="gradevance",
            name="GradeVance",
            version="0.1.0",
            entry_route="/apps/gradevance",
            required_capabilities=["gradevance:view"],
            description=(
                "Multi-domain assessment, LCT measurement, rubrics, coaching, "
                "and HITL learning on EduOS."
            ),
            icon="School",
            is_system=False,
            is_active=True,
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} GradeVance manifest slug={manifest.slug}"))
