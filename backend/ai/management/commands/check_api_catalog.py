"""Validate brand api_catalog ESS contract (ADR-0049).

    manage.py check_api_catalog [--instance nibras]
"""
from __future__ import annotations

import yaml
from django.core.management.base import BaseCommand, CommandError

from ai.engine.core.archetypes import get_instance_config_path
from ai.eval.api_catalog_contract import catalog_violations


class Command(BaseCommand):
    help = "Validate kind/not_for/empty_render on instance api_catalog entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--instance",
            default="nibras",
            help="Pack id (domain_packs/<id>/instance.yaml via pack.yaml)",
        )

    def handle(self, *args, **options):
        instance = options["instance"]
        path = get_instance_config_path(instance)
        if not path.is_file():
            raise CommandError(f"missing {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        catalog = list(data.get("api_catalog") or [])
        violations = catalog_violations(catalog)
        kinded = sum(1 for e in catalog if isinstance(e, dict) and e.get("kind"))
        if violations:
            for row in violations:
                self.stderr.write(row)
            raise CommandError(
                f"{len(violations)} api_catalog violation(s) in {instance}"
            )
        self.stdout.write(
            f"{kinded} kinded tools valid in {instance} "
            f"({len(catalog)} catalog entries)"
        )
