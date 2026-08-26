# dq/scorecard_service.py — DQ quality scorecard (EPH-3A).
#
# Aggregates DQResult records for a table by DAMA DMBOK2 dimension into a
# quality scorecard. All business logic lives here; views stay thin.
#
# domain-agnostic. MUST NOT import from emissions.
import logging

from dataschema.models import DataTable
from .models import DQResult, TableProfile

logger = logging.getLogger(__name__)

# The six core DAMA DMBOK2 dimensions surfaced in the scorecard (spec EPH-3A).
CORE_DIMENSIONS = [
    'completeness',
    'validity',
    'accuracy',
    'uniqueness',
    'consistency',
    'timeliness',
]


class ScorecardService:
    """Computes a quality scorecard for a table from its DQResults."""

    def compute_scorecard(self, table_id: int) -> dict:
        """Return the quality scorecard for a table.

        Pulls results via `DQResult.objects.filter(rule__field_assignments__data_table=table)`.
        Each result's verdict is bucketed by its rule's dimension. Results with
        passed=None (status=skipped_unavailable — Pulse down) are excluded from
        pass/fail counts (fail-visible), so scores honestly show the gap.
        """
        table = DataTable.objects.get(id=table_id)
        results = (
            DQResult.objects.filter(rule__field_assignments__data_table=table)
            .select_related('rule')
            .distinct()
        )

        # Seed the six core dimensions with zeros so a table with no results
        # (or no results for a dimension) reports honest zeros. Any other
        # dimension present in results is added dynamically so nothing is lost.
        dimensions = {
            dim: {'passed': 0, 'failed': 0, 'score': 0.0}
            for dim in CORE_DIMENSIONS
        }

        total_rules = 0
        last_run_at = None
        for result in results:
            if result.run_at is not None and (
                last_run_at is None or result.run_at > last_run_at
            ):
                last_run_at = result.run_at

            if result.passed is None:
                continue  # skipped_unavailable — excluded from pass/fail counts

            dim = result.rule.dimension if result.rule else 'validity'
            bucket = dimensions.setdefault(
                dim, {'passed': 0, 'failed': 0, 'score': 0.0}
            )
            total_rules += 1
            if result.passed:
                bucket['passed'] += 1
            else:
                bucket['failed'] += 1

        # Per-dimension score = passed / evaluated (0.0 when nothing evaluated).
        for bucket in dimensions.values():
            evaluated = bucket['passed'] + bucket['failed']
            bucket['score'] = round(bucket['passed'] / evaluated, 4) if evaluated else 0.0

        # Overall quality score: the weighted average of dimension scores,
        # weighted by the number of evaluated results in each dimension.
        evaluated_total = sum(b['passed'] + b['failed'] for b in dimensions.values())
        quality_score = (
            round(
                sum(b['passed'] for b in dimensions.values()) / evaluated_total,
                4,
            )
            if evaluated_total
            else 0.0
        )

        profile = (
            TableProfile.objects.filter(data_table=table)
            .order_by('-profiled_at').first()
        )
        profile_summary = {
            'row_count': profile.row_count if profile else 0,
            'completeness_pct': profile.completeness_pct if profile else 0.0,
            'profiled_at': profile.profiled_at.isoformat() if profile else None,
        }

        return {
            'quality_score': quality_score,
            'dimensions': dimensions,
            'total_rules': total_rules,
            'last_run_at': last_run_at.isoformat() if last_run_at else None,
            'profile_summary': profile_summary,
        }


def compute_scorecard(table_id: int) -> dict:
    """Module-level convenience entrypoint (spec signature)."""
    return ScorecardService().compute_scorecard(table_id)
