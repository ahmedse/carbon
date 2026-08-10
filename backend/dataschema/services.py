# File: dataschema/services.py
# Service layer for the dataschema app (Facade pattern).
# Views call these services; services return plain data (dict/list/str), never DRF
# Response objects. Zero behavioral change vs. the logic previously in views.

import io
import json

import pandas as pd

from .serializers import DataRowSerializer


class BulkImportService:
    """Bulk row import and template generation for DataTables."""

    @staticmethod
    def import_rows(data_table, file_data, column_mapping=None, created_by=None):
        """
        Parse a CSV/Excel upload and create DataRow records for the given table.

        Returns a results dict:
            {'created': int, 'failed': int, 'errors': [{'row': int, 'data': dict, 'error': str}, ...]}

        Raises ValueError with a user-facing message on file/parse/mapping errors
        (same messages the view previously returned as 400 responses).
        """
        # Parse file (CSV or Excel)
        if not (file_data.name.endswith('.csv') or file_data.name.endswith(('.xlsx', '.xls'))):
            raise ValueError('File must be CSV (.csv) or Excel (.xlsx, .xls)')

        try:
            file_content = file_data.read()
            if file_data.name.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_content))
            else:
                df = pd.read_excel(io.BytesIO(file_content))
        except Exception as e:
            raise ValueError(f'Failed to parse file: {str(e)}')

        # Apply column mapping if provided
        if column_mapping:
            try:
                column_mapping = json.loads(column_mapping)
                df = df.rename(columns=column_mapping)
            except json.JSONDecodeError:
                raise ValueError('column_mapping must be valid JSON')

        # Initialize results
        results = {
            'created': 0,
            'failed': 0,
            'errors': []
        }

        # Process each row
        fields = list(data_table.fields.filter(is_active=True, is_archived=False))
        for idx, row in df.iterrows():
            row_data = row.to_dict()

            # Remove NaN values (pandas represents empty cells as NaN)
            row_data = {k: v for k, v in row_data.items() if pd.notna(v)}

            # Remove 'id' column if present (Phase 1: create only)
            row_data.pop('id', None)

            # Pre-validate against field metadata (Level 1 — fast, no DB write)
            from .validators import validate_row
            field_errors = validate_row(row_data, fields)
            if field_errors:
                results['failed'] += 1
                results['errors'].append({
                    'row': idx + 2,  # +2 because: 0-indexed + header row
                    'data': row_data,
                    'error': '; '.join(
                        f"{e['field']}: {e['message']}" for e in field_errors
                    ),
                })
                continue  # skip serializer entirely for invalid rows

            # ── Level 2: DQ Gate (import mode) ────────────────────────
            from dq.gate import check_rows
            gate_result = check_rows(data_table, [row_data], mode='import')
            row_verdict = gate_result['row_verdicts'][0] if gate_result['row_verdicts'] else {'verdict': 'pass', 'failures': []}

            if row_verdict['verdict'] == 'block':
                results['dq_blocked'] += 1
                results['failed'] += 1
                rule_names = ', '.join(f['rule_name'] for f in row_verdict['failures'])
                results['errors'].append({
                    'row': idx + 2,
                    'data': row_data,
                    'error': f'DQ gate blocked: {rule_names}',
                })
                continue

            try:
                # Validate and create row
                serializer = DataRowSerializer(data={
                    'data_table': data_table.id,
                    'values': row_data
                })
                serializer.is_valid(raise_exception=True)
                instance = serializer.save(created_by=created_by)

                # Persist warn/info flags from gate
                if row_verdict['verdict'] != 'pass' and row_verdict['failures']:
                    from django.utils import timezone
                    new_flags = []
                    for f in row_verdict['failures']:
                        if f['severity'] in ('warn', 'info'):
                            new_flags.append({
                                'rule_id': f['rule_id'],
                                'rule_name': f['rule_name'],
                                'severity': f['severity'],
                                'message': f['message'],
                                'at': timezone.now().isoformat(),
                            })
                    if new_flags:
                        current = list(instance.dq_flags) if instance.dq_flags else []
                        current.extend(new_flags)
                        instance.dq_flags = current
                        instance.save(update_fields=['dq_flags'])
                        results['dq_flagged'] += 1

                results['created'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': idx + 2,  # +2 because: 0-indexed + header row
                    'data': row_data,
                    'error': str(e)
                })

        return results

    @staticmethod
    def generate_template(data_table, include_example=False):
        """
        Generate the blank CSV template string for a table.
        Returns the CSV content (str); the view wraps it in an HttpResponse.
        """
        # Get active fields ordered by position
        fields = data_table.fields.filter(is_active=True, is_archived=False).order_by('order')

        # Generate CSV header (use field names, not labels)
        headers = [f.name for f in fields]
        csv_rows = [','.join(f'"{h}"' for h in headers)]

        # Optionally add example row
        if include_example:
            example_values = []
            for f in fields:
                if f.type == 'string':
                    example_values.append('"example text"')
                elif f.type == 'text':
                    example_values.append('"example multiline text"')
                elif f.type == 'number':
                    example_values.append('123')
                elif f.type == 'date':
                    example_values.append('"2026-01-01"')
                elif f.type == 'boolean':
                    example_values.append('true')
                elif f.type == 'select':
                    options = f.options or []
                    if options:
                        example_values.append(f'"{options[0].get("value", "")}"')
                    else:
                        example_values.append('""')
                elif f.type == 'multiselect':
                    example_values.append('""')  # Empty for simplicity
                elif f.type == 'file':
                    example_values.append('""')  # Not supported in CSV import
                else:
                    example_values.append('""')
            csv_rows.append(','.join(example_values))

        return '\r\n'.join(csv_rows)


class SchemaValidationService:
    """Single-value validation against a DataField's type rules."""

    @staticmethod
    def validate_field(field, value):
        """
        Validate a single value against a DataField's type constraints.
        Delegates to the unified validate_row() for Level 1 validation.

        Returns None on success; raises ValueError with the same messages
        the serializer uses (as {field_name: message}).
        """
        from .validators import validate_row
        errors = validate_row({field.name: value}, [field])
        if errors:
            raise ValueError({errors[0]['field']: errors[0]['message']})
        return None
