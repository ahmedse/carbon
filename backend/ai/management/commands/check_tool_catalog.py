r"""Pulse 0.3 (Phase E2) — validate the domain tool catalog.

Checks every tool returned by each registered domain's ``get_tools()`` for the
CBAC + schema invariants the typed catalog requires:

  * non-empty ``description``
  * ``required_capability`` is ``None`` or a real key in ``ALL_CAPABILITIES``
  * ``input_schema`` is a dict containing ``"type": "object"``
  * ``id`` matches ``^{domain}\..+`` and ``domain`` is non-empty

Prints each violation to stderr and exits non-zero on any violation; prints
``N tools valid across M domains`` on success.

    manage.py check_tool_catalog
"""

import re

from django.core.management.base import BaseCommand, CommandError

from accounts.capabilities import ALL_CAPABILITIES
from ai.domain_protocol import get_domain, list_domains


class Command(BaseCommand):
    help = "Validate the CBAC metadata + schema of every registered domain tool."

    def handle(self, *args, **options):
        violations: list[str] = []
        total_tools = 0
        domains = list_domains()

        for app_id in sorted(domains):
            domain = get_domain(app_id)()
            for tool in domain.get_tools():
                total_tools += 1

                if not (tool.description or "").strip():
                    violations.append(f"{tool.id}: empty description")

                if (
                    tool.required_capability is not None
                    and tool.required_capability not in ALL_CAPABILITIES
                ):
                    violations.append(
                        f"{tool.id}: unknown required_capability "
                        f"'{tool.required_capability}'"
                    )

                if not isinstance(tool.input_schema, dict) or tool.input_schema.get(
                    "type"
                ) != "object":
                    violations.append(
                        f"{tool.id}: input_schema must be a dict with "
                        f"'type': 'object'"
                    )

                if not tool.domain:
                    violations.append(f"{tool.id}: empty domain")

                if not re.match(rf"^{re.escape(tool.domain)}\..+$", tool.id):
                    violations.append(
                        f"{tool.id}: id does not match ^{tool.domain}\\..+"
                    )

        if violations:
            for violation in violations:
                self.stderr.write(violation)
            raise CommandError(
                f"{len(violations)} tool catalog violation(s) across "
                f"{len(domains)} domain(s)."
            )

        self.stdout.write(
            f"{total_tools} tools valid across {len(domains)} domains"
        )
