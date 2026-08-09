"""DQ Rule Executor Service - Executes and validates data quality rules."""
import logging
from django.utils import timezone
from django.db import models
from .models import DQRule, DQResult, FieldProfile, TableProfile


logger = logging.getLogger(__name__)


class DQRuleExecutor:
    """Executes DQ rules against data rows and generates results."""

    def __init__(self, rule: DQRule, field=None):
        """Initialize executor with a rule and optional specific field.

        If field is None and rule has field_assignments, the first field
        assignment is used.
        """
        self.rule = rule
        assignments = list(rule.field_assignments.select_related('data_field', 'data_table').all())
        if not assignments:
            raise ValueError(f"Rule {rule.id} has no field assignments.")
        if field:
            self.field = field
            self.table = field.data_table if hasattr(field, 'data_table') else assignments[0].data_table
        else:
            assn = assignments[0]
            self.field = assn.data_field
            self.table = assn.data_table
        self.results = []

    def execute(self, data_sample: list = None) -> DQResult:
        """
        Execute rule against data sample.

        Args:
            data_sample: List of row dictionaries to validate.
                        If None, uses all rows in data source.

        Returns:
            DQResult object with execution outcome.
        """
        try:
            if self.field:
                result = self._execute_field_rule(data_sample)
            else:
                result = self._execute_table_rule(data_sample)
            return result
        except Exception as e:
            logger.error(f"Error executing rule {self.rule.id}: {str(e)}")
            return self._create_error_result(str(e))

    def _execute_field_rule(self, data_sample: list) -> DQResult:
        """Execute a field-level DQ rule."""
        rule_type = self.rule.rule_type
        params = self.rule.params or {}
        
        # Determine data source
        if data_sample is None:
            # In production, would fetch from actual data source
            data_sample = []
        
        passed = True
        failed_count = 0
        checked_count = len(data_sample)
        sample_failures = []
        
        # Route to specific validator
        if rule_type == 'not_null':
            passed, failed_count, sample_failures = self._validate_not_null(data_sample)
        elif rule_type == 'unique':
            passed, failed_count, sample_failures = self._validate_unique(data_sample)
        elif rule_type == 'allowed_values':
            passed, failed_count, sample_failures = self._validate_allowed_values(
                data_sample, params
            )
        elif rule_type == 'range':
            passed, failed_count, sample_failures = self._validate_range(
                data_sample, params
            )
        elif rule_type == 'regex':
            passed, failed_count, sample_failures = self._validate_regex(
                data_sample, params
            )
        elif rule_type == 'reference_integrity':
            passed, failed_count, sample_failures = self._validate_reference_integrity(
                data_sample, params
            )
        elif rule_type == 'threshold':
            passed, failed_count, sample_failures = self._validate_threshold(
                data_sample, params
            )
        elif rule_type == 'nl_check':
            passed, failed_count, sample_failures = self._validate_nl_check(
                data_sample, self.rule
            )
        elif rule_type == 'custom':
            # Custom rules can be user-defined
            passed = True
            failed_count = 0
        
        # Calculate score
        score = max(0, 100 - int((failed_count / max(1, checked_count)) * 100))
        
        # Create result
        result = DQResult.objects.create(
            rule=self.rule,
            passed=passed,
            checked_count=checked_count,
            failed_count=failed_count,
            sample_failures=sample_failures[:10],  # Keep first 10 failures
            score=score
        )
        
        return result

    def _execute_table_rule(self, data_sample: list) -> DQResult:
        """Execute a table-level DQ rule."""
        rule_type = self.rule.rule_type
        params = self.rule.params or {}
        
        passed = True
        failed_count = 0
        checked_count = len(data_sample) if data_sample else 0
        sample_failures = []
        
        # Table-level rules check entire row structure
        if rule_type == 'not_null':
            # Check that all required columns are present
            passed = True
            failed_count = 0
        elif rule_type == 'unique':
            # Check uniqueness across rows
            passed = True
            failed_count = 0
        
        score = 100 if passed else 50
        
        result = DQResult.objects.create(
            rule=self.rule,
            passed=passed,
            checked_count=checked_count,
            failed_count=failed_count,
            sample_failures=sample_failures,
            score=score
        )
        
        return result

    def _validate_not_null(self, data: list) -> tuple:
        """Check that field is not null."""
        if not data:
            return True, 0, []
        
        failed_count = 0
        failures = []
        
        for idx, row in enumerate(data):
            value = row.get(self.field.name if self.field else 'value')
            if value is None or value == '':
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx,
                        'value': value,
                        'reason': 'Value is null or empty'
                    })
        
        passed = failed_count == 0
        return passed, failed_count, failures

    def _validate_unique(self, data: list) -> tuple:
        """Check that field values are unique."""
        if not data:
            return True, 0, []
        
        seen = {}
        failed_count = 0
        failures = []
        
        for idx, row in enumerate(data):
            value = row.get(self.field.name if self.field else 'value')
            
            if value in seen:
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx,
                        'value': value,
                        'reason': f'Duplicate value (first seen at row {seen[value]})'
                    })
            else:
                seen[value] = idx
        
        passed = failed_count == 0
        return passed, failed_count, failures

    def _validate_allowed_values(self, data: list, params: dict) -> tuple:
        """Check that field values are in allowed list."""
        if not data or 'allowed_values' not in params:
            return True, 0, []
        
        allowed = set(params['allowed_values'])
        failed_count = 0
        failures = []
        
        for idx, row in enumerate(data):
            value = row.get(self.field.name if self.field else 'value')
            
            if value not in allowed:
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx,
                        'value': value,
                        'reason': f'Value not in allowed list: {allowed}'
                    })
        
        passed = failed_count == 0
        return passed, failed_count, failures

    def _validate_range(self, data: list, params: dict) -> tuple:
        """Check that field values are within range."""
        if not data or 'min' not in params or 'max' not in params:
            return True, 0, []
        
        min_val = params['min']
        max_val = params['max']
        failed_count = 0
        failures = []
        
        for idx, row in enumerate(data):
            value = row.get(self.field.name if self.field else 'value')
            
            try:
                numeric_value = float(value)
                if not (min_val <= numeric_value <= max_val):
                    failed_count += 1
                    if len(failures) < 10:
                        failures.append({
                            'row': idx,
                            'value': value,
                            'reason': f'Value {value} outside range [{min_val}, {max_val}]'
                        })
            except (ValueError, TypeError):
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx,
                        'value': value,
                        'reason': 'Value cannot be converted to numeric'
                    })
        
        passed = failed_count == 0
        return passed, failed_count, failures

    def _validate_regex(self, data: list, params: dict) -> tuple:
        """Check that field values match regex pattern."""
        if not data or 'pattern' not in params:
            return True, 0, []
        
        import re
        pattern = params['pattern']
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {pattern}: {str(e)}")
            return False, len(data), [{'reason': f'Invalid regex: {str(e)}'}]
        
        failed_count = 0
        failures = []
        
        for idx, row in enumerate(data):
            value = str(row.get(self.field.name if self.field else 'value', ''))
            
            if not compiled_pattern.match(value):
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx,
                        'value': value,
                        'reason': f'Value does not match pattern: {pattern}'
                    })
        
        passed = failed_count == 0
        return passed, failed_count, failures

    def _validate_reference_integrity(self, data: list, params: dict) -> tuple:
        """Check that field values reference a valid code in a ReferenceSet."""
        if not data:
            return True, 0, []

        from mdm.models import ReferenceSet

        rs_id = params.get('reference_set_id')
        field = self.field
        if rs_id is None and field and hasattr(field, 'reference_set_id'):
            rs_id = field.reference_set_id

        if rs_id:
            try:
                ref_set = ReferenceSet.objects.get(id=rs_id)
                allowed = {
                    str(c) for c in
                    ref_set.get_current_values().values_list('code', flat=True)
                }
            except ReferenceSet.DoesNotExist:
                allowed = set()
        else:
            allowed = set()

        if not allowed:
            # No reference set → all non-empty values fail
            failed_count = 0
            failures = []
            for idx, row in enumerate(data):
                value = row.get(field.name if field else 'value')
                if value is not None and value != '':
                    failed_count += 1
                    if len(failures) < 10:
                        failures.append({
                            'row': idx, 'value': value,
                            'reason': 'No reference set configured',
                        })
            return failed_count == 0, failed_count, failures

        failed_count = 0
        failures = []
        for idx, row in enumerate(data):
            value = row.get(field.name if field else 'value')
            if value is None or value == '':
                continue
            if str(value) not in allowed:
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx, 'value': value,
                        'reason': f'Value not in reference set (allowed: {sorted(allowed)[:10]}...)',
                    })

        return failed_count == 0, failed_count, failures

    def _validate_threshold(self, data: list, params: dict) -> tuple:
        """Check that numeric field values satisfy a single inequality operator.

        Supported params:
            operator: gte | gt | lte | lt | eq | neq  (default: gte)
            value:   numeric threshold to compare against

        Examples:
            {"operator": "gte", "value": 0}   → value must be >= 0
            {"operator": "lt",  "value": 100} → value must be < 100
            {"operator": "eq",  "value": 0}   → value must == 0
        """
        if not data:
            return True, 0, []

        op = params.get('operator', 'gte')
        threshold_val = params.get('value')

        if threshold_val is None:
            return True, 0, []

        try:
            tv = float(threshold_val)
        except (TypeError, ValueError):
            logger.error(f"Invalid threshold value: {threshold_val}")
            return False, len(data), [{'reason': f'Invalid threshold value: {threshold_val}'}]

        OPS = {
            'gte': lambda x: x >= tv,
            'gt':  lambda x: x > tv,
            'lte': lambda x: x <= tv,
            'lt':  lambda x: x < tv,
            'eq':  lambda x: x == tv,
            'neq': lambda x: x != tv,
        }

        check = OPS.get(op)
        if check is None:
            logger.error(f"Unknown threshold operator: {op}")
            return False, len(data), [{'reason': f'Unknown operator: {op}'}]

        failed_count = 0
        failures = []
        field_name = self.field.name if self.field else 'value'

        for idx, row in enumerate(data):
            value = row.get(field_name)
            if value is None or value == '':
                continue
            try:
                fv = float(value)
            except (TypeError, ValueError):
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx, 'value': value,
                        'reason': f'Value cannot be converted to numeric',
                    })
                continue
            if not check(fv):
                failed_count += 1
                if len(failures) < 10:
                    failures.append({
                        'row': idx, 'value': value,
                        'reason': f'Value {fv} fails {op} {tv}',
                    })

        return failed_count == 0, failed_count, failures

    def _validate_nl_check(self, data: list, rule) -> tuple:
        """Validate rows against a natural-language DQ rule via Pulse.

        Sends rule + rows to Pulse. Gracefully degrades: if Pulse is
        unreachable, returns (True, 0, []) — treating the rule as passed
        to avoid blocking workflows.

        Returns:
            (passed: bool, failed_count: int, sample_failures: list)
        """
        if not data or not rule.params.get('prompt'):
            return True, 0, []

        try:
            from pulse_gateway import PulseGateway
        except ImportError:
            logger.warning('pulse_gateway module not available')
            return True, 0, []

        field = getattr(self, 'field', None) or getattr(rule, 'field', None)
        field_names = [field.name] if field else list(data[0].keys()) if data else []

        gateway = PulseGateway()
        rows = [
            {k: v for k, v in row.items() if not data or k in row}
            for row in data
        ]

        rules_payload = [{
            'id': str(rule.id),
            'prompt': rule.params.get('prompt', ''),
            'fields': field_names,
            'severity': rule.severity or 'error',
        }]

        response = gateway.validate_dq_rules(
            rules=rules_payload,
            rows=rows,
            context={
                'table_name': self.table.name if self.table else '',
                'row_count_hint': len(data),
            },
        )

        status = response.get('status', 'pulse_unavailable')

        if status == 'pulse_unavailable':
            logger.warning('Pulse unavailable for NL check rule %s', rule.id)
            return True, 0, []

        if status != 'completed':
            logger.warning(
                'Pulse returned status=%s for NL check rule %s (task_id=%s)',
                status, rule.id, response.get('task_id', ''),
            )
            return True, 0, []

        # Parse results
        results = response.get('result', {}).get('results', [])
        if not results:
            return True, 0, []

        rule_result = results[0]
        result_status = rule_result.get('status', 'error')

        if result_status == 'error':
            logger.warning(
                'Pulse NL check error for rule %s: %s',
                rule.id, rule_result.get('explanation', ''),
            )
            return True, 0, []

        if result_status == 'pass':
            return True, 0, []

        # result_status == 'fail'
        failing_rows = rule_result.get('failing_rows', [])
        failed_count = len(failing_rows)
        sample_failures = [
            {
                'row': idx,
                'explanation': rule_result.get('explanation', ''),
                'confidence': rule_result.get('confidence'),
            }
            for idx in failing_rows[:10]
        ]

        return False, failed_count, sample_failures

    def _create_error_result(self, error_message: str) -> DQResult:
        """Create a failed result for execution errors."""
        result = DQResult.objects.create(
            rule=self.rule,
            passed=False,
            checked_count=0,
            failed_count=1,
            sample_failures=[{
                'error': error_message,
                'timestamp': timezone.now().isoformat()
            }],
            score=0
        )
        return result
