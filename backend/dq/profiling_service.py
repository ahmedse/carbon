# dq/profiling_service.py — DQ profiling service (EPH-3A).
#
# Populates the EXISTING TableProfile + FieldProfile models (dq/models.py)
# via update_or_create. All business logic lives here; views stay thin.
#
# domain-agnostic. MUST NOT import from emissions.
import logging
from statistics import mean

from django.utils import timezone

from dataschema.models import DataTable, DataRow
from .models import TableProfile, FieldProfile

logger = logging.getLogger(__name__)

# Load at most this many rows per profile run (spec: up to 10_000 DataRow).
MAX_ROWS = 10_000
# Number of most-frequent values captured per field.
TOP_VALUES_LIMIT = 10


def _is_empty(value) -> bool:
    """Treat None / '' / [] as missing (mirrors the existing DQ convention)."""
    return value is None or value == '' or value == []


class ProfilingService:
    """Computes table/field profiles and persists them to TableProfile/FieldProfile."""

    def profile_table(self, table_id: int) -> dict:
        """Profile a table's rows and update/create its profile records.

        For each active DataField: null_count, distinct_count, min/max (all
        types), mean (numeric only), and the top-10 values by frequency.
        A single TableProfile plus one FieldProfile per field is created or
        updated (update_or_create), never duplicated.
        """
        table = DataTable.objects.get(id=table_id)
        rows = list(
            DataRow.objects.filter(data_table=table, is_archived=False)[:MAX_ROWS]
        )
        n = len(rows)
        fields = list(table.fields.filter(is_active=True, is_archived=False))

        null_counts = {}
        distinct_counts = {}
        min_values = {}
        max_values = {}
        mean_values = {}
        completeness_all = []

        # Legacy runs may have left duplicate FieldProfile rows; update_or_create()
        # calls get() internally and raises MultipleObjectsReturned on duplicates.
        # Collapse to the single latest row per field first.
        for field in fields:
            stale_ids = list(
                FieldProfile.objects.filter(data_field=field)
                .order_by('-profiled_at').values_list('id', flat=True)[1:]
            )
            if stale_ids:
                FieldProfile.objects.filter(id__in=stale_ids).delete()

        for field in fields:
            values = [r.values.get(field.name) for r in rows]
            non_empty = [v for v in values if not _is_empty(v)]
            null_count = n - len(non_empty)
            distinct = len({str(v) for v in non_empty})
            completeness = (len(non_empty) / n * 100) if n else 0.0
            uniqueness = (distinct / len(non_empty) * 100) if non_empty else 0.0
            completeness_all.append(completeness)

            min_value = ''
            max_value = ''
            mean_value = None
            if field.type == 'number':
                nums = []
                for v in non_empty:
                    try:
                        nums.append(float(v))
                    except (TypeError, ValueError):
                        pass
                if nums:
                    min_value = str(min(nums))
                    max_value = str(max(nums))
                    mean_value = mean(nums)

            counts = {}
            for v in non_empty:
                key = str(v)
                counts[key] = counts.get(key, 0) + 1
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:TOP_VALUES_LIMIT]

            FieldProfile.objects.update_or_create(
                data_field=field,
                defaults={
                    'row_count': n,
                    'null_count': null_count,
                    'distinct_count': distinct,
                    'completeness_pct': round(completeness, 2),
                    'uniqueness_pct': round(uniqueness, 2),
                    'min_value': min_value,
                    'max_value': max_value,
                    'mean_value': mean_value,
                    'top_values': [{'value': k, 'count': c} for k, c in top],
                    'profiled_at': timezone.now(),
                },
            )

            null_counts[field.name] = null_count
            distinct_counts[field.name] = distinct
            min_values[field.name] = min_value if min_value != '' else None
            max_values[field.name] = max_value if max_value != '' else None
            mean_values[field.name] = mean_value

        table_completeness = round(mean(completeness_all), 2) if completeness_all else 0.0

        # Collapse duplicate TableProfile rows (legacy runs), then update_or_create
        # the single latest row.
        stale_ids = list(
            TableProfile.objects.filter(data_table=table)
            .order_by('-profiled_at').values_list('id', flat=True)[1:]
        )
        if stale_ids:
            TableProfile.objects.filter(id__in=stale_ids).delete()
        table_profile, _ = TableProfile.objects.update_or_create(
            data_table=table,
            defaults={
                'row_count': n,
                'completeness_pct': table_completeness,
                'null_counts': null_counts,
                'distinct_counts': distinct_counts,
                'min_values': min_values,
                'max_values': max_values,
                'mean_values': mean_values,
                'profiled_at': timezone.now(),
            },
        )

        logger.info(
            'Table profiling completed',
            extra={
                'table_id': table.id,
                'rows_profiled': n,
                'fields_profiled': len(fields),
                'completeness_pct': table_completeness,
            },
        )

        return {
            'table_id': table.id,
            'row_count': n,
            'completeness_pct': table_completeness,
            'profiled_at': table_profile.profiled_at.isoformat(),
            'field_profiles': [
                {
                    'field_id': field.id,
                    'field_name': field.name,
                    'null_count': null_counts[field.name],
                    'distinct_count': distinct_counts[field.name],
                    'min_value': min_values[field.name],
                    'max_value': max_values[field.name],
                    'mean_value': mean_values[field.name],
                }
                for field in fields
            ],
        }


def profile_table(table_id: int) -> dict:
    """Module-level convenience entrypoint (spec signature)."""
    return ProfilingService().profile_table(table_id)
