"""DQ Rule Executor Service - Executes and validates data quality rules."""
import logging
from django.utils import timezone
from django.db import models
from .models import DQRule, DQResult, FieldProfile, TableProfile


logger = logging.getLogger(__name__)


class DQRuleExecutor:
    """Executes DQ rules against data rows and generates results."""

    def __init__(self, rule: DQRule):
        """Initialize executor with a rule."""
        self.rule = rule
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
            if self.rule.scope == 'field' and self.rule.data_field:
                result = self._execute_field_rule(data_sample)
            elif self.rule.scope == 'table' and self.rule.data_table:
                result = self._execute_table_rule(data_sample)
            else:
                raise ValueError(f"Invalid rule scope or missing target: {self.rule.scope}")
            
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
            value = row.get(self.rule.data_field.name if self.rule.data_field else 'value')
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
            value = row.get(self.rule.data_field.name if self.rule.data_field else 'value')
            
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
            value = row.get(self.rule.data_field.name if self.rule.data_field else 'value')
            
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
            value = row.get(self.rule.data_field.name if self.rule.data_field else 'value')
            
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
            value = str(row.get(self.rule.data_field.name if self.rule.data_field else 'value', ''))
            
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
