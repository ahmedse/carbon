# File: emissions/models.py
# Emission factor database models for carbon calculations.

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


def _as_date(value):
    """Normalize a date or ISO date-string to a datetime.date.

    Django 5.x leaves raw strings on model __init__ assignment (to_python only
    runs on DB read / full_clean), so freshly-created ReportingPeriod /
    EmissionFactor instances may hold 'YYYY-MM-DD' strings. Guard every place
    that does arithmetic on these values.
    """
    from datetime import date as _date
    if value is None or isinstance(value, _date):
        return value
    if isinstance(value, str):
        return _date.fromisoformat(value)
    return value


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
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
    ]
    
    # Identity
    name = models.CharField(max_length=100, help_text="e.g., 'FY 2025', 'Q1 2025'")
    
    # Period dates
    start_date = models.DateField(help_text="Start date of the reporting period")
    end_date = models.DateField(help_text="End date of the reporting period")
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='annual')
    
    # Status and workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Metadata
    description = models.TextField(blank=True, help_text="Optional description or notes")
    is_baseline = models.BooleanField(default=False, help_text="Is this the baseline period for comparisons?")

    # GHG Protocol: Organizational boundary
    organizational_boundary = models.ForeignKey(
        'OrganizationalBoundary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reporting_periods',
        help_text="Organizational boundary for this reporting period"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
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
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
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

    # ── State machine ──────────────────────────────────────────────────

    VALID_TRANSITIONS = {
        'draft': ['open'],
        'open': ['locked'],
        'locked': ['submitted', 'open'],
        'submitted': ['verified', 'rejected'],
        'rejected': ['submitted'],
        'verified': ['closed'],
        'closed': [],
    }

    def can_transition_to(self, new_status):
        """Return True if the requested status transition is permitted."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status, user=None):
        """Advance the reporting period status with validation and optional audit emission."""
        if new_status == self.status:
            return self
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition: {self.status} -> {new_status}"
            )
        old_status = self.status
        self.status = new_status
        update_fields = ['status']
        if new_status == 'submitted':
            from django.utils import timezone
            self.submitted_at = timezone.now()
            update_fields.append('submitted_at')
        self.save(update_fields=update_fields)

        if user is not None:
            from catalog.audit_utils import emit_governance_event
            emit_governance_event(
                entity_type='ReportingPeriod',
                entity_id=self.id,
                action='transition',
                before={'status': old_status},
                after={'status': self.status},
                user=user,
            )
        return self


class VerificationRecord(models.Model):
    """Tracks verification actions on reporting periods."""
    reporting_period = models.ForeignKey(
        'ReportingPeriod', on_delete=models.CASCADE, related_name='verifications'
    )
    verifier = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_review', 'In Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
    )
    notes = models.TextField(blank=True, default='')
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('reporting_period', 'verifier')]

    def __str__(self):
        return f"Verification #{self.id} — {self.reporting_period.name} ({self.get_status_display()})"


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

    # GHG Protocol: Scope 2 dual calculation tag
    scope2_method = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[('location_based', 'Location-Based'), ('market_based', 'Market-Based')],
        help_text="For Scope 2 calculations: which method produced this result"
    )

    # GHG Protocol: emission factor version snapshot at calculation time
    emission_factor_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of the emission factor values used at calculation time"
    )
    factor_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the emission factor was applied"
    )

    # Activity data quality rollup
    @property
    def data_quality_tier(self):
        """Inherit quality tier from the calculation rule that produced this result."""
        rule = self.emission_factor.calculation_rules.first() if self.emission_factor else None
        return rule.data_quality_tier if rule else None

    @property
    def quality_score(self):
        """Normalized quality score 0–100 based on IPCC tier and factor precision."""
        tier = self.data_quality_tier or 1
        base = {1: 50, 2: 75, 3: 100}.get(tier, 50)
        # Small bonus if factor had per-gas breakdown
        if self.co2_kg is not None or self.ch4_kg is not None:
            base = min(base + 5, 100)
        return base

    # Integrity tracking (E3-3)
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supersedes',
        help_text="Points to the replacement Calculation that supersedes this one"
    )
    is_stale = models.BooleanField(
        default=False,
        help_text="True if the emission factor used has been edited since this calculation was created"
    )
    
    class Meta:
        ordering = ['-calculated_at']
        verbose_name = "Emission Calculation"
        verbose_name_plural = "Emission Calculations"
        indexes = [
            models.Index(fields=['module', 'scope', 'reporting_year']),
            models.Index(fields=['module', 'reporting_year']),
            models.Index(fields=['category', 'reporting_year']),
            models.Index(fields=['reporting_period']),
            models.Index(fields=['activity_date']),
            models.Index(fields=['is_stale'], name='calc_is_stale_idx'),
        ]
    
    def __str__(self):
        return f"{self.activity_value} {self.activity_unit} → {self.co2e_kg} kg CO2e"
    
    @classmethod
    def create_from_data_row(cls, data_row, emission_factor, activity_value, activity_unit, 
                             reporting_year, reporting_month=None, reporting_period=None,
                             activity_date=None, calculated_by=None, scope2_method=None,
                             emission_factor_snapshot=None):
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
        ef_decimal = Decimal(str(emission_factor.factor_value))
        co2e = activity_decimal * ef_decimal
        
        # Calculate individual gas components if available
        co2_kg = None
        ch4_kg = None
        n2o_kg = None
        
        if emission_factor.co2_factor:
            co2_kg = activity_decimal * Decimal(str(emission_factor.co2_factor))
        if emission_factor.ch4_factor:
            ch4_kg = activity_decimal * Decimal(str(emission_factor.ch4_factor))
        if emission_factor.n2o_factor:
            n2o_kg = activity_decimal * Decimal(str(emission_factor.n2o_factor))
        
        # If reporting_period provided, extract year from it if not explicitly given
        if reporting_period and not reporting_year:
            reporting_year = _as_date(reporting_period.start_date).year
        
        return cls.objects.create(
            data_row=data_row,
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
            calculation_method='auto',
            scope2_method=scope2_method,
            emission_factor_snapshot=emission_factor_snapshot,
            factor_applied_at=timezone.now() if emission_factor_snapshot else None,
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

    # GHG Protocol: Scope 2 dual calculation
    SCOPE2_METHOD_CHOICES = [
        ('location_based', 'Location-Based'),
        ('market_based', 'Market-Based'),
        ('dual', 'Both (Location + Market)'),
    ]
    scope2_calculation_method = models.CharField(
        max_length=20,
        choices=SCOPE2_METHOD_CHOICES,
        default='location_based',
        help_text="Scope 2 calculation method per GHG Protocol: location-based (grid avg), market-based (contractual), or both"
    )

    # GHG Protocol: Activity data quality tier (IPCC 2006 Guidelines)
    DATA_QUALITY_TIER_CHOICES = [
        (1, 'Tier 1 — Default/IER factors'),
        (2, 'Tier 2 — Country-specific factors'),
        (3, 'Tier 3 — Facility-specific / direct measurement'),
    ]
    data_quality_tier = models.PositiveSmallIntegerField(
        choices=DATA_QUALITY_TIER_CHOICES,
        default=1,
        help_text="IPCC data quality tier for the activity data feeding this rule"
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

        # E3-3: also ensure the default factor is active
        if ef and not ef.is_active:
            return None  # silently skip — inactive factors must not produce calculations

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

        # E3-3: Enforce factor validity window against activity date
        if ef:
            check_date = activity_date or (timezone.now().date())

            # Guard: Django .create() with string dates may leave them as str
            def _dt(v):
                if v is None:
                    return None
                if isinstance(v, str):
                    from datetime import date
                    return date.fromisoformat(v)
                return v

            vf = _dt(ef.valid_from)
            vt = _dt(ef.valid_to)
            if vt and vt < check_date:
                return None  # factor expired
            if vf and vf > check_date:
                return None  # factor not yet valid
        
        # Determine reporting year
        reporting_year = None
        
        # Try to extract year from period_month (e.g. "2024-01")
        period_month_raw = data_row.values.get('period_month')
        period_year = None
        period_month_num = None
        if isinstance(period_month_raw, str) and len(period_month_raw) >= 7:
            try:
                parts = period_month_raw.split('-')
                if len(parts) >= 2:
                    period_year = int(parts[0])
                    period_month_num = int(parts[1])
            except (ValueError, IndexError):
                pass
        
        if reporting_period:
            reporting_year = _as_date(reporting_period.start_date).year
        elif activity_date:
            reporting_year = activity_date.year
        elif period_year:
            reporting_year = period_year
        else:
            reporting_year = timezone.now().year
        
        # Extract reporting month from DataRow values
        reporting_month = None
        # First try period_month (structured)
        if period_month_num and 1 <= period_month_num <= 12:
            reporting_month = period_month_num
        else:
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

        # Build emission factor version snapshot (GHG Protocol 2.5)
        ef_snapshot = {
            'factor_id': ef.id,
            'factor_code': ef.code,
            'factor_name': ef.name,
            'factor_value': str(ef.factor_value),
            'factor_unit': ef.factor_unit,
            'activity_unit': ef.activity_unit,
            'source': ef.source,
            'valid_from': str(ef.valid_from) if ef.valid_from else None,
            'valid_to': str(ef.valid_to) if ef.valid_to else None,
            'co2_factor': str(ef.co2_factor) if ef.co2_factor else None,
            'ch4_factor': str(ef.ch4_factor) if ef.ch4_factor else None,
            'n2o_factor': str(ef.n2o_factor) if ef.n2o_factor else None,
            'snapshot_at': timezone.now().isoformat(),
        }

        # GHG Protocol: Scope 2 dual calculation
        results = []
        scope2_mode = self.scope2_calculation_method if ef.scope == 2 else 'location_based'

        if scope2_mode in ('location_based', 'dual'):
            results.append(Calculation.create_from_data_row(
                data_row=data_row,
                emission_factor=ef,
                activity_value=activity_value,
                activity_unit=ef.activity_unit,
                reporting_year=reporting_year,
                reporting_month=reporting_month,
                reporting_period=reporting_period,
                activity_date=activity_date,
                calculated_by=user,
                scope2_method='location_based',
                emission_factor_snapshot=ef_snapshot,
            ))

        if scope2_mode in ('market_based', 'dual'):
            # Try to find a market-based counterpart factor
            market_ef = ef
            if self.factor_selector_mapping and '__market__' in self.factor_selector_mapping:
                market_code = self.factor_selector_mapping['__market__']
                market_ef = EmissionFactor.objects.filter(code=market_code, is_active=True).first() or ef

            results.append(Calculation.create_from_data_row(
                data_row=data_row,
                emission_factor=market_ef,
                activity_value=activity_value,
                activity_unit=market_ef.activity_unit,
                reporting_year=reporting_year,
                reporting_month=reporting_month,
                reporting_period=reporting_period,
                activity_date=activity_date,
                calculated_by=user,
                scope2_method='market_based',
                emission_factor_snapshot=ef_snapshot,
            ))

        # Return the first (primary) calculation for backward compatibility;
        # dual results are accessible via the Calculation model queryset.
        return results[0] if results else None
    
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
                    # NOTE: no write-back into row.values — DataRow is
                    # append-only (immutable evidence, dataschema.models
                    # _MUTABLE_FIELDS). The result is already persisted by
                    # calculate_for_row via Calculation.create_from_data_row,
                    # which is the canonical audit trail for output values.
                else:
                    skipped += 1
            except Exception as e:
                errors += 1

        # Trigger DQ profiling when new calculations were created
        if created > 0:
            from dq.services import profile_table, run_dq
            try:
                profile_table(self.data_table_id)
                run_dq(self.data_table_id)
            except Exception:
                pass  # DQ failures must not block calculation results

        return created, skipped, errors


class ReportConfig(models.Model):
    """
    Saved report configuration for reusable report generation.
    Captures: which period, which org_unit subtree, which GHG scopes,
    which categories, and output format preferences.
    """
    PERIOD_TYPE_CHOICES = [
        ('existing', 'Existing Reporting Period'),
        ('custom', 'Custom Date Range'),
    ]
    FORMAT_CHOICES = [
        ('json', 'JSON'),
        ('csv', 'CSV'),
    ]
    GROUPING_CHOICES = [
        ('scope', 'By GHG Scope'),
        ('category', 'By Category'),
        ('module', 'By Module'),
        ('month', 'By Month'),
    ]

    name = models.CharField(max_length=200, help_text="e.g., 'FY 2026 Smart Village Annual Report'")
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='report_configs'
    )

    # Period selection
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="If null, use custom_start / custom_end"
    )
    custom_start = models.DateField(null=True, blank=True)
    custom_end = models.DateField(null=True, blank=True)

    # Scope filters
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Scope to this org_unit subtree (null = all accessible)"
    )
    ghg_scopes = models.JSONField(
        default=list,
        help_text="List of GHG scope numbers to include, e.g., [1, 2, 3]. Empty = all."
    )
    categories = models.JSONField(
        default=list,
        help_text="List of category codes to include. Empty = all."
    )

    # Output preferences
    output_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='json')
    grouping = models.CharField(max_length=20, choices=GROUPING_CHOICES, default='scope')
    include_dq_status = models.BooleanField(default=True)
    include_unverified = models.BooleanField(default=False)

    # Metadata
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Report Configuration"
        verbose_name_plural = "Report Configurations"

    def __str__(self):
        return self.name


class SBTiTarget(models.Model):
    """Science-Based Target initiative target — emission reduction goal per org unit."""
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.CASCADE, related_name='sbti_targets'
    )
    name = models.CharField(max_length=200)
    base_year = models.IntegerField()
    target_year = models.IntegerField()
    target_type = models.CharField(
        max_length=20,
        choices=[('absolute', 'Absolute Reduction'), ('intensity', 'Intensity Reduction')]
    )
    scope = models.CharField(
        max_length=20,
        choices=[
            ('1', 'Scope 1'),
            ('2', 'Scope 2'),
            ('3', 'Scope 3'),
            ('1+2', 'Scope 1+2'),
            ('1+2+3', 'Scope 1+2+3'),
        ]
    )
    reduction_pct = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('committed', 'Committed'),
            ('approved', 'Approved'),
        ],
        default='draft',
    )
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sbti_targets_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-base_year']

    def __str__(self):
        return f"{self.name} ({self.base_year}→{self.target_year}, -{self.reduction_pct}%)"


class CalculationAudit(models.Model):
    """Immutable audit trail for every calculation trigger event."""
    TRIGGER_TYPE_CHOICES = [
        ('single', 'Single Rule'),
        ('batch', 'Batch'),
    ]

    trigger_type = models.CharField(max_length=10, choices=TRIGGER_TYPE_CHOICES)
    triggered_by = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT,
        help_text="User who triggered this calculation run"
    )
    calculation_rule = models.ForeignKey(
        CalculationRule, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Rule executed (null for batch)"
    )
    data_table = models.ForeignKey(
        'dataschema.DataTable', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="DataTable targeted"
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Reporting period for this run"
    )
    table_ids = models.JSONField(
        null=True, blank=True,
        help_text="List of table IDs for batch runs"
    )
    recalculate = models.BooleanField(default=False)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    triggered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['-triggered_at']),
            models.Index(fields=['triggered_by', '-triggered_at']),
            models.Index(fields=['reporting_period']),
        ]

    def __str__(self):
        return f"Audit #{self.id} — {self.get_trigger_type_display()} by {self.triggered_by} ({self.created_count}c/{self.skipped_count}s/{self.error_count}e)"


class ExportAudit(models.Model):
    """Immutable audit trail for every report export.

    Records who exported what, when, with which parameters, and the resulting file size.
    Written per generated report so admins can trace data exfiltration.
    """
    exported_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="User who triggered the export"
    )
    exported_at = models.DateTimeField(auto_now_add=True)
    report_format = models.CharField(max_length=20, help_text="e.g., 'xlsx', 'csv', 'json'")
    config_hash = models.CharField(max_length=64, help_text="SHA-256 hash of the report config parameters")
    period_id = models.PositiveIntegerField(null=True, blank=True)
    org_unit_id = models.PositiveIntegerField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    grouping = models.CharField(max_length=20, blank=True, default='scope')
    row_count = models.PositiveIntegerField(default=0)
    file_size_bytes = models.PositiveIntegerField(default=0, help_text="Size of the generated file in bytes")

    class Meta:
        verbose_name = "Export Audit"
        verbose_name_plural = "Export Audits"
        ordering = ['-exported_at']
        indexes = [
            models.Index(fields=['-exported_at'], name='export_audit_exported_at_idx'),
            models.Index(fields=['exported_by', '-exported_at'], name='export_audit_exported_by_idx'),
        ]

    def __str__(self):
        return f"Export #{self.id} — {self.report_format} by {self.exported_by} ({self.row_count} rows)"


# ═══════════════════════════════════════════════════════════════════════════
# GHG Protocol Phase 2 Models
# ═══════════════════════════════════════════════════════════════════════════


class OrganizationalBoundary(models.Model):
    """
    GHG Protocol organizational boundary definition.

    Defines which entities, assets, and operations are included in the
    GHG inventory and under which consolidation approach per the
    GHG Protocol Corporate Standard, Chapter 3.
    """

    CONSOLIDATION_APPROACH_CHOICES = [
        ('equity_share', 'Equity Share'),
        ('financial_control', 'Financial Control'),
        ('operational_control', 'Operational Control'),
    ]

    name = models.CharField(max_length=200, help_text="e.g., 'AASTMT Equity Share Boundary'")
    consolidation_approach = models.CharField(
        max_length=30,
        choices=CONSOLIDATION_APPROACH_CHOICES,
        default='operational_control',
        help_text="GHG Protocol consolidation approach"
    )
    description = models.TextField(
        blank=True,
        help_text="Narrative description of entities/assets included/excluded"
    )
    included_org_units = models.ManyToManyField(
        'mdm.OrgUnit',
        blank=True,
        related_name='organizational_boundaries',
        help_text="Org units within this boundary"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_boundaries',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Organizational Boundary"
        verbose_name_plural = "Organizational Boundaries"
        indexes = [
            models.Index(fields=['consolidation_approach']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_consolidation_approach_display()})"


class BaseYear(models.Model):
    """
    GHG Protocol base year definition with recalculation policy.

    Per GHG Protocol Corporate Standard, Chapter 5: companies shall
    choose a base year against which future emissions are compared.
    A base year recalculation policy defines when adjustments are required.
    """

    RECALC_POLICY_CHOICES = [
        ('significant_only', 'Recalculate only for significant changes'),
        ('all_changes', 'Recalculate for all structural changes'),
        ('never', 'Fixed base year — do not recalculate'),
    ]

    year = models.PositiveIntegerField(help_text="Base year (e.g., 2024)")
    reporting_period = models.OneToOneField(
        ReportingPeriod,
        on_delete=models.PROTECT,
        related_name='base_year',
        help_text="Reporting period serving as the base year"
    )
    recalculation_policy = models.CharField(
        max_length=30,
        choices=RECALC_POLICY_CHOICES,
        default='significant_only',
        help_text="Policy for when base year emissions should be recalculated"
    )
    significance_threshold_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        help_text="Significance threshold (%) that triggers recalculation"
    )
    description = models.TextField(blank=True, help_text="Rationale for base year selection")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-year']
        verbose_name = "Base Year"
        verbose_name_plural = "Base Years"
        constraints = [
            models.UniqueConstraint(
                fields=['year'],
                condition=models.Q(is_active=True),
                name='unique_active_base_year',
            ),
        ]

    def __str__(self):
        return f"Base Year {self.year} — {self.reporting_period.name if self.reporting_period else 'N/A'}"


class RecalculationTrigger(models.Model):
    """
    Records an event that triggers base year recalculation per GHG Protocol.

    Types:
    - structural_change: merger, acquisition, divestiture
    - methodology_change: improved emission factor, new calculation method
    - error_correction: significant error discovered in base year data
    - threshold_exceeded: significance threshold crossed
    """

    TRIGGER_TYPE_CHOICES = [
        ('structural_change', 'Structural Change'),
        ('methodology_change', 'Methodology Change'),
        ('error_correction', 'Error Correction'),
        ('threshold_exceeded', 'Significance Threshold Exceeded'),
    ]

    RESOLUTION_CHOICES = [
        ('open', 'Open — Requires Recalculation'),
        ('in_progress', 'In Progress'),
        ('recalculated', 'Recalculated'),
        ('dismissed', 'Dismissed'),
    ]

    base_year = models.ForeignKey(
        BaseYear,
        on_delete=models.CASCADE,
        related_name='recalculation_triggers',
    )
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES)
    description = models.TextField(help_text="Description of the event that triggered recalculation")
    variance_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Measured variance from base year (%)"
    )
    resolution_status = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        default='open',
    )
    resolution_notes = models.TextField(blank=True)

    triggered_at = models.DateTimeField(auto_now_add=True)
    triggered_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-triggered_at']
        verbose_name = "Recalculation Trigger"
        verbose_name_plural = "Recalculation Triggers"
        indexes = [
            models.Index(fields=['base_year', 'resolution_status']),
            models.Index(fields=['trigger_type']),
        ]

    def __str__(self):
        return f"Trigger #{self.id}: {self.get_trigger_type_display()} — {self.get_resolution_status_display()}"
