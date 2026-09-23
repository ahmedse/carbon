# Registry: Backend Services & Utilities  (auto-generated 2026-09-23 10:44 — DO NOT EDIT)

> Business logic lives in services. Before writing a new one, check this list — extend, don't duplicate.

## Service classes
```
backend/accounts/services.py:107:class PulseService:
backend/accounts/services.py:17:class RoleResolutionService:
backend/accounts/services.py:61:class AppManifestService:
backend/ai/audit_service.py:23:class AuditService:
backend/ai/catalog_service.py:60:class CatalogService:
backend/ai/durable_service.py:101:class DurableExecutionService:
backend/ai/plans_service.py:833:class PlansService:
backend/ai/subagent_service.py:68:class SubagentService:
backend/appregistry/services.py:13:class AppRegistryService:
backend/connections/services.py:22:class ConnectionService:
backend/core/services.py:12:class NotificationService:
backend/core/tests/test_notifications.py:44:class NotificationServiceTests(TestCase):
backend/dataschema/masking.py:5:class MaskingService:
backend/dataschema/services.py:14:class BulkImportService:
backend/dataschema/services.py:181:class SchemaValidationService:
backend/dataschema/tests/test_validate_row.py:419:class ValidateRowViaServiceTests(TestCase):
backend/dq/profiling_service.py:28:class ProfilingService:
backend/dq/scorecard_service.py:25:class ScorecardService:
backend/emissions/services.py:1001:class OwnerService:
backend/emissions/services.py:1212:class MyDataService:
backend/emissions/services.py:1340:class ConsoleService:
backend/emissions/services.py:1490:class ReportConfigService:
backend/emissions/services.py:1493:class TargetService:
backend/emissions/services.py:154:class DashboardService:
backend/emissions/services.py:1584:class ReportConfigService:
backend/emissions/services.py:1699:class VerificationService:
backend/emissions/services.py:1770:class PeriodLockService:
backend/emissions/services.py:1812:class InventoryCoverageService:
backend/emissions/services.py:1894:class ChairmanService:
backend/emissions/services.py:261:class YearlyComparisonService:
backend/emissions/services.py:419:class ReportService:
backend/emissions/services.py:59:class CalculationSummaryService:
backend/emissions/services.py:764:class CalculationEngineService:
backend/emissions/tests/test_calculation_summary.py:21:class CalculationSummaryServicePeriodFallbackTests(TestCase):
backend/emissions/tests/test_inventory_coverage.py:88:class InventoryCoverageServiceTests(TestCase):
backend/emissions/tests/test_services.py:119:class OwnerServiceTests(TestCase):
backend/emissions/tests/test_services.py:137:class YearlyComparisonServiceTests(TestCase):
backend/emissions/tests/test_services.py:165:class ReportServiceTests(TestCase):
backend/emissions/tests/test_services.py:212:class CalculationEngineServiceExtendedTests(TestCase):
backend/emissions/tests/test_services.py:21:class CalculationEngineServiceTests(TestCase):
backend/emissions/tests/test_services.py:255:class OwnerServiceExtendedTests(TestCase):
backend/emissions/tests/test_services.py:286:class MyDataServiceTests(TestCase):
backend/emissions/tests/test_services.py:319:class ConsoleServiceTests(TestCase):
backend/emissions/tests/test_services.py:347:class ReportConfigServiceTests(TestCase):
backend/emissions/tests/test_services.py:376:class TargetServiceExtendedTests(TestCase):
backend/emissions/tests/test_services.py:76:class TargetServiceTests(TestCase):
backend/emissions/tests/test_services.py:95:class DashboardServiceTests(TestCase):
backend/evidence/services.py:9:class EvidenceService:
backend/gradevance/services/pack_bump.py:32:class PackBumpService:
backend/gradevance/services/pipeline.py:1098:class ReviewService:
backend/gradevance/services/pipeline.py:845:class FormativePipelineService:
backend/gradevance/services/repin.py:33:class ProfileRepinService:
backend/healthy/services.py:134:class ERPSnapshotService:
backend/healthy/services.py:249:class HealthyPipelineService:
backend/healthy/services.py:408:class LoadoutService:
backend/healthy/services.py:453:class DashboardService:
backend/importexport/services.py:20:class ImportService:
backend/importexport/services.py:78:class ExportService:
backend/mdm/services.py:190:class OrgUnitService:
backend/mdm/services.py:79:class ReferenceSetService:
backend/people/compensation_service.py:22:class CompensationService:
backend/people/loan_service.py:24:class LoanServiceError(Exception):
backend/people/payroll_service.py:142:class PayrollRunService:
backend/people/payroll_service.py:41:class PayrollServiceError(Exception):
backend/people/services.py:13:class CalculationService:
backend/people/tests/test_host_sod.py:123:class WpsSoDServiceTests(TestCase):
backend/people/tests/test_host_sod.py:82:class PayrollSoDServiceTests(TestCase):
backend/people/tests/test_payroll_service.py:161:class PayrollRunServiceTests(TestCase):
```

## Management commands
```
backend/accounts/management/commands/apply_brand.py
backend/accounts/management/commands/backfill_scoped_roles.py
backend/accounts/management/commands/bootstrap_platform.py
backend/accounts/management/commands/ensure_eduos_admins.py
backend/accounts/management/commands/ensure_nibras_admins.py
backend/accounts/management/commands/populate_demo_users.py
backend/accounts/management/commands/provision_alamein_rbac.py
backend/accounts/management/commands/run_backup.py
backend/accounts/management/commands/seed_rbac.py
backend/ai/management/commands/check_tool_catalog.py
backend/ai/management/commands/ensure_pulse_instance.py
backend/ai/management/commands/learn_from_feedback.py
backend/ai/management/commands/reconcile_outcomes.py
backend/ai/management/commands/run_cognition_loop.py
backend/ai/management/commands/run_dq_feedback_loop.py
backend/ai/management/commands/run_due_schedules.py
backend/ai/management/commands/run_learning_loop.py
backend/ai/management/commands/run_pulse_maintenance.py
backend/ai/management/commands/seed_ai_demo.py
backend/ai/management/commands/seed_catalog_skills.py
backend/ai/management/commands/seed_complex_agent_demos.py
backend/ai/management/commands/seed_nibras_knowledge.py
backend/ai/management/commands/seed_nibras_processes.py
backend/ai/management/commands/seed_ops_canvas_examples.py
backend/ai/management/commands/simulate_agent_workflows.py
backend/ai/management/commands/simulate_nibras_operator_processes.py
backend/ai/management/commands/simulate_nibras_pulse_processes.py
backend/appregistry/management/commands/activate_apps.py
backend/appregistry/management/commands/register_app.py
backend/core/management/commands/deploy_aastmt.py
backend/core/management/commands/flush_carbon.py
backend/core/management/commands/seed_aastmt_data.py
backend/core/management/commands/seed_aastmt_org.py
backend/core/management/commands/seed_aastmt_showcase.py
backend/core/management/commands/seed_carbon_coverage.py
backend/core/management/commands/seed_carbon_metadata.py
backend/core/management/commands/seed_carbon_raw.py
backend/correspondence/management/commands/reroute_orphaned_correspondence.py
backend/correspondence/management/commands/seed_correspondence.py
backend/dq/management/commands/check_freshness.py
backend/dq/management/commands/profile_all.py
backend/dq/management/commands/schema_snapshot.py
backend/emissions/management/commands/seed_carbon_reference_data.py
backend/emissions/management/commands/seed_demo_data.py
backend/emissions/management/commands/seed_emission_factors.py
backend/emissions/management/commands/setup_carbon_app.py
backend/emissions/management/commands/sync_carbon_catalog.py
backend/emissions/management/commands/unlock_tables.py
backend/gradevance/management/commands/bump_gradevance_pack.py
backend/gradevance/management/commands/gradevance_gold_eval.py
backend/gradevance/management/commands/gradevance_lti_readiness.py
backend/gradevance/management/commands/mine_gradevance_proposals.py
backend/gradevance/management/commands/register_gradevance_app.py
backend/gradevance/management/commands/seed_gradevance_demo.py
backend/gradevance/management/commands/seed_wave10_demo.py
backend/gradevance/management/commands/soak_gradevance_lti.py
backend/gradevance/management/commands/sync_eduos_packs.py
backend/healthy/management/commands/register_healthy_app.py
backend/mdm/management/commands/seed_gofsco_org.py
backend/people/management/commands/apply_gofsco_kuwaitization.py
backend/people/management/commands/assign_employee_managers.py
backend/people/management/commands/backfill_salary_estimates.py
backend/people/management/commands/import_gofsco_employees.py
backend/people/management/commands/link_employee_users.py
backend/people/management/commands/normalize_employee_genders.py
backend/people/management/commands/propagate_leave_policies.py
backend/people/management/commands/seed_gofsco.py
backend/people/management/commands/seed_gofsco_rules.py
backend/people/management/commands/seed_people_dq.py
backend/people/management/commands/seed_test_rules.py
backend/regulations/management/commands/run_audit.py
backend/regulations/management/commands/seed_regulations.py
```
