# File: people/management/commands/normalize_employee_genders.py
# Canonically normalize raw ``M``/``F`` gender variants on Employee.gender.
#
# ``Employee.gender`` is free text (NOT a governed enum), so dirty imports can
# leave ``M``/``F``/``Male``/``FEMALE`` etc. behind. This command defensively
# collapses those to the canonical lowercase ``male``/``female`` tokens while
# leaving blanks untouched (never invent a gender) and unknown non-blank values
# unchanged (surfaced as ``skipped_unknown`` for operator review).
#
# Idempotent: only rows whose normalized value actually differs are written, so
# a second run reports 0 changes.
#
# Usage:
#   ./manage.py normalize_employee_genders [--dry-run]

from django.core.management.base import BaseCommand

from people.models import Employee

# Canonical gender map (after ``.strip().lower()``). Anything not in this map
# and not blank is treated as unknown and left unchanged.
CANONICAL_GENDER = {
    "m": "male",
    "male": "male",
    "f": "female",
    "female": "female",
}


def normalize_gender(raw: str) -> str:
    """Return the canonical gender for a raw value, or the raw value unchanged.

    Blanks (``''``) stay blank; unknown non-blank values are returned verbatim
    so callers can decide whether to update them.
    """
    key = (raw or "").strip().lower()
    if key == "":
        return ""
    return CANONICAL_GENDER.get(key, raw)


class Command(BaseCommand):
    help = (
        "Canonically normalize Employee.gender: M/m/Male/MALE → male, "
        "F/f/Female/FEMALE → female. Blanks stay blank and unknown values are "
        "left unchanged (reported). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        stats = {
            "total": 0,
            "blank": 0,
            "already_canonical": 0,
            "normalized_m": 0,
            "normalized_f": 0,
            "skipped_unknown": 0,
            "skipped_unknown_values": set(),
        }

        for emp in Employee.objects.all().iterator():
            stats["total"] += 1
            stored = emp.gender or ""
            stripped = stored.strip()
            key = stripped.lower()

            if key == "":
                # Blank or whitespace-only → canonical blank. Never invent a gender.
                stats["blank"] += 1
                if stripped != stored and not dry_run:
                    emp.gender = ""
                    emp.save(update_fields=["gender"])
                continue

            canonical = CANONICAL_GENDER.get(key)
            if canonical is None:
                # Unknown non-blank value — leave unchanged, surface for review.
                stats["skipped_unknown"] += 1
                stats["skipped_unknown_values"].add(stored)
                continue

            if stripped == canonical:
                # Already exactly canonical (e.g. "male"/"female") — no-op.
                stats["already_canonical"] += 1
                continue

            # Known variant that differs from canonical (e.g. "m", "Male", "FEMALE").
            if canonical == "male":
                stats["normalized_m"] += 1
            else:
                stats["normalized_f"] += 1

            if not dry_run:
                emp.gender = canonical
                emp.save(update_fields=["gender"])

        changes = stats["normalized_m"] + stats["normalized_f"]
        unknown_values = sorted(stats["skipped_unknown_values"])

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] would process {stats['total']} employees "
                    f"({changes} to normalize: "
                    f"{stats['normalized_m']} m→male, "
                    f"{stats['normalized_f']} f→female)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Gender normalization complete: {stats['total']} employees, "
                    f"{changes} normalized "
                    f"({stats['normalized_m']} m→male, "
                    f"{stats['normalized_f']} f→female)."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Unchanged: {stats['blank']} blank, "
                f"{stats['already_canonical']} already canonical."
            )
        )

        if stats["skipped_unknown"]:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Skipped {stats['skipped_unknown']} unknown non-blank "
                    f"value(s) (left unchanged): {', '.join(repr(v) for v in unknown_values)}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✓ No unknown non-blank values to review.")
            )
