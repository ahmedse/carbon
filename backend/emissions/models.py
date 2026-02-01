# File: emissions/models.py
# Emission factor database models for carbon calculations.

from django.db import models
from django.core.exceptions import ValidationError


class ReportingPeriod(models.Model):
    """
    Defines a reporting cycle with configurable start and end dates.
    
    Examples:
    - Calendar Year 2025: Jan 1, 2025 - Dec 31, 2025
    - Fiscal Year 2025: Apr 1, 2024 - Mar 31, 2025
    - Q1 2025: Jan 1, 2025 - Mar 31, 2025
    """
    
    PERIOD_TYPE_CHOICES = [
        ('annual', 'Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open for Data Entry'),
        ('locked', 'Locked for Review'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('closed', 'Closed'),
    ]
    
    # Identity
    name = models.CharField(max_length=100, help_text="e.g., 'FY 2025', 'Q1 2025'")
    
    # Tenant/Project scope
    tenant = models.ForeignKey(
        'accounts.Tenant',
        on_delete=models.CASCADE,
        related_name='reporting_periods',
        help_text="Tenant this period belongs to"
    )
    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reporting_periods',
        help_text="Optional: specific project (if null, applies to all tenant projects)"
    )
    
    # Period dates
    start_date = models.DateField(help_text="Start date of the reporting period")
    end_date = models.DateField(help_text="End date of the reporting period")
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='annual')
    
    # Status and workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Metadata
    description = models.TextField(blank=True, help_text="Optional description or notes")
    is_baseline = models.BooleanField(default=False, help_text="Is this the baseline period for comparisons?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_reporting_periods'
    )
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Reporting Period"
        verbose_name_plural = "Reporting Periods"
        indexes = [
            models.Index(fields=['tenant', 'start_date', 'end_date']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_after_start_date'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        """Validate that end_date is after start_date."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})
    
    @property
    def duration_days(self):
        """Return the number of days in this period."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None
    
    @property
    def is_active(self):
        """Check if current date falls within this period."""
        from django.utils import timezone
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class EmissionFactor(models.Model):
    """
    Stores emission conversion factors for calculating CO2e.
    Examples: 
    - Electricity (kWh) → kg CO2e
    - Diesel (liters) → kg CO2e
    - Flight (km) → kg CO2e
    """
    
    # Categories
    CATEGORY_CHOICES = [
        ('electricity', 'Electricity Grid'),
        ('stationary_combustion', 'Stationary Combustion'),
        ('mobile_combustion', 'Mobile Combustion'),
        ('fugitive', 'Fugitive Emissions'),
        ('process', 'Process Emissions'),
        ('transport', 'Transportation'),
        ('waste', 'Waste'),
        ('water', 'Water'),
        ('materials', 'Materials/Products'),
    ]
    
    SCOPE_CHOICES = [
        (1, 'Scope 1 - Direct'),
        (2, 'Scope 2 - Indirect (Energy)'),
        (3, 'Scope 3 - Value Chain'),
    ]
    
    # Identity
    name = models.CharField(max_length=200, help_text="Descriptive name, e.g., 'US Grid Average 2024'")
    code = models.CharField(max_length=50, unique=True, help_text="Unique code, e.g., 'US_GRID_2024'")
    
    # Classification
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    subcategory = models.CharField(max_length=100, blank=True, help_text="e.g., 'Natural Gas'")
    scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES)
    
    # Factor Details
    factor_value = models.DecimalField(
        max_digits=20, 
        decimal_places=10,
        help_text="Emission factor value (kg CO2e per activity unit)"
    )
    factor_unit = models.CharField(max_length=50, default="kg CO2e", help_text="e.g., 'kg CO2e'")
    activity_unit = models.CharField(max_length=50, help_text="e.g., 'kWh', 'liter', 'km'")
    
    # GHG Breakdown (optional - for detailed reporting)
    co2_factor = models.DecimalField(
        max_digits=20, 
        decimal_places=10, 
        null=True, 
        blank=True,
        help_text="CO2 component of the emission factor"
    )
    ch4_factor = models.DecimalField(
        max_digits=20, 
        decimal_places=10, 
        null=True, 
        blank=True,
        help_text="CH4 component (in CO2e)"
    )
    n2o_factor = models.DecimalField(
        max_digits=20, 
        decimal_places=10, 
        null=True, 
        blank=True,
        help_text="N2O component (in CO2e)"
    )
    
    # Geographic Scope
    country = models.CharField(max_length=100, blank=True, help_text="e.g., 'United States'")
    country_code = models.CharField(max_length=3, blank=True, help_text="ISO 3166-1 alpha-3, e.g., 'USA'")
    region = models.CharField(max_length=100, blank=True, help_text="e.g., 'California'")
    
    # Source & Validity
    source = models.CharField(max_length=200, help_text="Data source, e.g., 'EPA eGRID 2024'")
    source_url = models.URLField(blank=True, help_text="URL to source documentation")
    valid_from = models.DateField(help_text="Start date of validity period")
    valid_to = models.DateField(null=True, blank=True, help_text="End date of validity period (optional)")
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Additional notes or methodology details")
    is_active = models.BooleanField(default=True, help_text="Whether this factor is currently in use")
    
    # Smart matching tags for dynamic field binding
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords for smart matching with DataFields, e.g., ['electricity', 'grid', 'kwh']"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Emission Factor"
        verbose_name_plural = "Emission Factors"
        indexes = [
            models.Index(fields=['category', 'country_code']),
            models.Index(fields=['scope']),
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.factor_value} {self.factor_unit}/{self.activity_unit})"
    
    def calculate_emissions(self, activity_value):
        """
        Calculate emissions for a given activity value.
        
        Args:
            activity_value: The amount of activity (e.g., kWh consumed)
            
        Returns:
            Decimal: CO2e in kg
        """
        from decimal import Decimal
        return Decimal(str(activity_value)) * self.factor_value


class GWP(models.Model):
    """
    Global Warming Potentials for different greenhouse gases.
    Used to convert CH4, N2O, HFCs, etc. to CO2 equivalent.
    
    Values from IPCC Assessment Reports (AR5 and AR6).
    """
    gas_name = models.CharField(max_length=100, help_text="e.g., 'Methane'")
    gas_formula = models.CharField(max_length=50, help_text="Chemical formula, e.g., 'CH4'")
    
    # GWP values from different assessment reports
    gwp_ar5_100yr = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="GWP from IPCC AR5 (100-year horizon)"
    )
    gwp_ar6_100yr = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="GWP from IPCC AR6 (100-year horizon)"
    )
    gwp_ar5_20yr = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="GWP from IPCC AR5 (20-year horizon)"
    )
    gwp_ar6_20yr = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="GWP from IPCC AR6 (20-year horizon)"
    )
    
    # Metadata
    cas_number = models.CharField(max_length=20, blank=True, help_text="CAS Registry Number")
    notes = models.TextField(blank=True, help_text="Additional notes about this gas")
    
    class Meta:
        verbose_name = "Global Warming Potential"
        verbose_name_plural = "Global Warming Potentials"
        ordering = ['gas_name']
    
    def __str__(self):
        return f"{self.gas_name} ({self.gas_formula}) - GWP: {self.gwp_ar6_100yr or self.gwp_ar5_100yr}"
    
    def get_gwp(self, ar_version='ar6', time_horizon=100):
        """
        Get the GWP value for specified AR version and time horizon.
        
        Args:
            ar_version: 'ar5' or 'ar6'
            time_horizon: 20 or 100 years
            
        Returns:
            Decimal or None: The GWP value
        """
        field_name = f'gwp_{ar_version}_{time_horizon}yr'
        return getattr(self, field_name, None)


class Calculation(models.Model):
    """
    Stores calculated emissions for a data row.
    Links activity data to emission factors and results.
    
    This model provides an audit trail of all emission calculations
    and supports detailed GHG Protocol reporting by scope and category.
    """
    
    # Link to source data
    data_row = models.ForeignKey(
        'dataschema.DataRow', 
        on_delete=models.CASCADE, 
        related_name='calculations',
        help_text="The source data row for this calculation"
    )
    project = models.ForeignKey(
        'core.Project', 
        on_delete=models.CASCADE, 
        related_name='calculations',
        help_text="The project this calculation belongs to"
    )
    module = models.ForeignKey(
        'core.Module', 
        on_delete=models.CASCADE, 
        related_name='calculations',
        help_text="The module (data collection unit) for this calculation"
    )
    
    # Emission factor used
    emission_factor = models.ForeignKey(
        EmissionFactor, 
        on_delete=models.PROTECT,
        help_text="The emission factor applied for this calculation"
    )
    
    # Calculation inputs
    activity_value = models.DecimalField(
        max_digits=20, 
        decimal_places=6,
        help_text="The activity amount (e.g., kWh, liters, km)"
    )
    activity_unit = models.CharField(max_length=50, help_text="Unit of activity")
    
    # Results
    co2e_kg = models.DecimalField(
        max_digits=20, 
        decimal_places=6,
        help_text="Total CO2 equivalent emissions in kg"
    )
    co2_kg = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="CO2 emissions in kg"
    )
    ch4_kg = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="CH4 emissions in kg CO2e"
    )
    n2o_kg = models.DecimalField(
        max_digits=20, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="N2O emissions in kg CO2e"
    )
    
    # Classification (denormalized for fast querying)
    scope = models.PositiveSmallIntegerField(
        choices=EmissionFactor.SCOPE_CHOICES,
        help_text="GHG Protocol scope (1, 2, or 3)"
    )
    category = models.CharField(max_length=50, help_text="Emission category")
    
    # Reporting period - supports both legacy (year/month) and new (ReportingPeriod)
    reporting_period = models.ForeignKey(
        ReportingPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='calculations',
        help_text="The reporting period/cycle this calculation belongs to"
    )
    # Legacy fields for backward compatibility
    reporting_year = models.PositiveIntegerField(help_text="Year for this emission data")
    reporting_month = models.PositiveSmallIntegerField(
        null=True, 
        blank=True,
        help_text="Month (1-12) if available"
    )
    # Activity date for precise time-series tracking
    activity_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the activity occurred"
    )
    
    # Audit
    calculated_at = models.DateTimeField(auto_now_add=True)
    calculated_by = models.ForeignKey(
        'accounts.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="User who triggered this calculation"
    )
    calculation_method = models.CharField(
        max_length=100, 
        default='auto',
        help_text="Method used: 'auto', 'manual', 'import', etc."
    )
    
    class Meta:
        ordering = ['-calculated_at']
        verbose_name = "Emission Calculation"
        verbose_name_plural = "Emission Calculations"
        indexes = [
            models.Index(fields=['project', 'scope', 'reporting_year']),
            models.Index(fields=['module', 'reporting_year']),
            models.Index(fields=['category', 'reporting_year']),
            models.Index(fields=['reporting_period']),
            models.Index(fields=['activity_date']),
        ]
    
    def __str__(self):
        return f"{self.activity_value} {self.activity_unit} → {self.co2e_kg} kg CO2e"
    
    @classmethod
    def create_from_data_row(cls, data_row, emission_factor, activity_value, activity_unit, 
                             reporting_year, reporting_month=None, reporting_period=None,
                             activity_date=None, calculated_by=None):
        """
        Factory method to create a calculation from a data row.
        
        Args:
            data_row: DataRow instance
            emission_factor: EmissionFactor to use
            activity_value: Amount of activity
            activity_unit: Unit of activity
            reporting_year: Year for reporting (legacy, extracted from period if not provided)
            reporting_month: Optional month (legacy)
            reporting_period: ReportingPeriod instance (preferred)
            activity_date: Date when activity occurred
            calculated_by: User who triggered the calculation
            
        Returns:
            Calculation: The created calculation instance
        """
        from decimal import Decimal
        
        activity_decimal = Decimal(str(activity_value))
        co2e = activity_decimal * emission_factor.factor_value
        
        # Calculate individual gas components if available
        co2_kg = None
        ch4_kg = None
        n2o_kg = None
        
        if emission_factor.co2_factor:
            co2_kg = activity_decimal * emission_factor.co2_factor
        if emission_factor.ch4_factor:
            ch4_kg = activity_decimal * emission_factor.ch4_factor
        if emission_factor.n2o_factor:
            n2o_kg = activity_decimal * emission_factor.n2o_factor
        
        # If reporting_period provided, extract year from it if not explicitly given
        if reporting_period and not reporting_year:
            reporting_year = reporting_period.start_date.year
        
        return cls.objects.create(
            data_row=data_row,
            project=data_row.data_table.module.project,
            module=data_row.data_table.module,
            emission_factor=emission_factor,
            activity_value=activity_decimal,
            activity_unit=activity_unit,
            co2e_kg=co2e,
            co2_kg=co2_kg,
            ch4_kg=ch4_kg,
            n2o_kg=n2o_kg,
            scope=emission_factor.scope,
            category=emission_factor.category,
            reporting_period=reporting_period,
            reporting_year=reporting_year,
            reporting_month=reporting_month,
            activity_date=activity_date,
            calculated_by=calculated_by,
            calculation_method='auto'
        )


class CalculationRule(models.Model):
    """
    Links a DataField (dynamic schema) to an EmissionFactor for automatic calculation.
    
    This enables the system to automatically calculate emissions when data is entered
    into any dynamic DataTable, without hardcoding column names.
    
    Example:
    - DataTable: "Monthly Electricity Usage"
    - DataField: "kwh_consumed" (type: number)
    - EmissionFactor: US_GRID_AVG (0.417 kg CO2e/kWh)
    - Output: Calculate CO2e automatically when user enters kWh value
    """
    
    RULE_TYPE_CHOICES = [
        ('direct', 'Direct Multiplication'),  # activity_value * factor
        ('unit_convert', 'With Unit Conversion'),  # Convert units first
        ('formula', 'Custom Formula'),  # Future: complex formulas
    ]
    
    # Source: Which DataField contains the activity data
    data_table = models.ForeignKey(
        'dataschema.DataTable',
        on_delete=models.CASCADE,
        related_name='calculation_rules',
        help_text="The data table this rule applies to"
    )
    activity_field = models.ForeignKey(
        'dataschema.DataField',
        on_delete=models.CASCADE,
        related_name='calculation_rules_as_activity',
        help_text="The field containing activity data (e.g., kWh, liters)"
    )
    
    # Optional: Field containing the activity date for time-series
    date_field = models.ForeignKey(
        'dataschema.DataField',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculation_rules_as_date',
        help_text="Optional: field containing the date of activity"
    )
    
    # Emission Factor to apply
    emission_factor = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        related_name='calculation_rules',
        help_text="The emission factor to apply"
    )
    
    # OR: Dynamic emission factor selection based on another field
    # (e.g., if user selects "Country" in a dropdown, pick the matching grid factor)
    factor_selector_field = models.ForeignKey(
        'dataschema.DataField',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculation_rules_as_selector',
        help_text="Optional: field that determines which emission factor to use"
    )
    factor_selector_mapping = models.JSONField(
        null=True,
        blank=True,
        help_text="Mapping from field value to EmissionFactor code, e.g., {'USA': 'US_GRID_AVG'}"
    )
    
    # Output: Where to store the calculated result
    output_field = models.ForeignKey(
        'dataschema.DataField',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculation_rules_as_output',
        help_text="Optional: field to store calculated CO2e (if null, stored in Calculation model only)"
    )
    
    # Rule configuration
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES, default='direct')
    unit_conversion_factor = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=1,
        help_text="Multiply activity value by this before applying emission factor"
    )
    custom_formula = models.TextField(
        blank=True,
        help_text="Future: Python expression for complex calculations"
    )
    
    # Metadata
    name = models.CharField(max_length=200, help_text="Descriptive name for this rule")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    auto_calculate = models.BooleanField(
        default=True,
        help_text="Automatically calculate when data is saved"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['data_table', 'name']
        verbose_name = "Calculation Rule"
        verbose_name_plural = "Calculation Rules"
        indexes = [
            models.Index(fields=['data_table', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name}: {self.activity_field.label} × {self.emission_factor.code}"
    
    def calculate_for_row(self, data_row, reporting_period=None, user=None):
        """
        Calculate emissions for a single DataRow using this rule.
        
        Args:
            data_row: DataRow instance
            reporting_period: Optional ReportingPeriod
            user: User who triggered the calculation
            
        Returns:
            Calculation instance or None if calculation failed
        """
        from decimal import Decimal, InvalidOperation
        
        # Get activity value from the row's JSON values
        activity_field_name = self.activity_field.name
        raw_value = data_row.values.get(activity_field_name)
        
        if raw_value is None or raw_value == '':
            return None
        
        try:
            activity_value = Decimal(str(raw_value)) * self.unit_conversion_factor
        except (InvalidOperation, ValueError):
            return None
        
        # Determine which emission factor to use
        ef = self.emission_factor
        if self.factor_selector_field and self.factor_selector_mapping:
            selector_value = data_row.values.get(self.factor_selector_field.name)
            if selector_value and selector_value in self.factor_selector_mapping:
                ef_code = self.factor_selector_mapping[selector_value]
                ef = EmissionFactor.objects.filter(code=ef_code, is_active=True).first() or ef
        
        # Get activity date if specified
        activity_date = None
        if self.date_field:
            date_value = data_row.values.get(self.date_field.name)
            if date_value:
                from datetime import datetime
                try:
                    if isinstance(date_value, str):
                        activity_date = datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
                    else:
                        activity_date = date_value
                except (ValueError, TypeError):
                    pass
        
        # Determine reporting year
        reporting_year = None
        if reporting_period:
            reporting_year = reporting_period.start_date.year
        elif activity_date:
            reporting_year = activity_date.year
        else:
            from django.utils import timezone
            reporting_year = timezone.now().year
        
        # Extract reporting month from DataRow values
        reporting_month = None
        month_value = data_row.values.get('reporting_month') or data_row.values.get('month')
        if month_value:
            # Map month names to numbers
            MONTH_MAP = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            if isinstance(month_value, str) and month_value in MONTH_MAP:
                reporting_month = MONTH_MAP[month_value]
            elif isinstance(month_value, int) and 1 <= month_value <= 12:
                reporting_month = month_value
        # Fallback to activity_date month
        if reporting_month is None and activity_date:
            reporting_month = activity_date.month
        
        # Create the calculation
        return Calculation.create_from_data_row(
            data_row=data_row,
            emission_factor=ef,
            activity_value=activity_value,
            activity_unit=ef.activity_unit,
            reporting_year=reporting_year,
            reporting_month=reporting_month,
            reporting_period=reporting_period,
            activity_date=activity_date,
            calculated_by=user
        )
    
    def calculate_for_table(self, reporting_period=None, user=None, recalculate=False):
        """
        Calculate emissions for all rows in the linked DataTable.
        
        Args:
            reporting_period: Optional ReportingPeriod
            user: User who triggered the calculation
            recalculate: If True, delete existing calculations first
            
        Returns:
            tuple: (created_count, skipped_count, error_count)
        """
        from dataschema.models import DataRow
        
        created = 0
        skipped = 0
        errors = 0
        
        rows = DataRow.objects.filter(
            data_table=self.data_table,
            is_archived=False
        )
        
        for row in rows:
            # Check if already calculated (skip unless recalculating)
            if not recalculate:
                existing = Calculation.objects.filter(
                    data_row=row,
                    emission_factor=self.emission_factor
                ).exists()
                if existing:
                    skipped += 1
                    continue
            else:
                # Delete existing calculations for this rule
                Calculation.objects.filter(
                    data_row=row,
                    emission_factor=self.emission_factor
                ).delete()
            
            try:
                result = self.calculate_for_row(row, reporting_period, user)
                if result:
                    created += 1
                    
                    # Optionally write back to output field
                    if self.output_field:
                        row.values[self.output_field.name] = float(result.co2e_kg)
                        row.save(update_fields=['values', 'updated_at'])
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
        
        return created, skipped, errors
