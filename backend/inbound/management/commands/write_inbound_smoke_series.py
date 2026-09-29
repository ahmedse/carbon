"""Write the inbound smoke series from stored envelopes.

The file is local evidence. Do not commit it. An empty selection does not
create the file. The excellence collector only reads the result.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from inbound.observe import series_batches, write_smoke_series

DEFAULT_SERIES = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "migration"
    / "evidence"
    / "inbound-smoke-series.json"
)


class Command(BaseCommand):
    help = "Write docs/migration/evidence/inbound-smoke-series.json from saved smoke envelopes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help="Override the output path. Tests pass a temporary file.",
        )

    def handle(self, *args, **options):
        batches = series_batches()
        if not batches:
            self.stdout.write("no smoked or committed envelopes; file not written")
            return
        path = Path(options["path"]) if options["path"] else DEFAULT_SERIES
        write_smoke_series(path, batches)
        self.stdout.write(f"wrote {len(batches)} rows to {path}")
