"""Healthy Foods Factory services (DESIGN-PLATFORM.md §8.3 / §8.5).

Responsibilities:
  * ``ERPSnapshotService`` — read-only extract from the legacy Healthy ERP,
    behind the ``connections.DataSource`` seam. Dev/tests use a recorded
    snapshot; the live path is strictly read-only (SELECT only, no DDL/DML).
  * ``HealthyPipelineService`` — the 5 healthy pipelines, each
    snapshot → DatasetVersion (DQ) → TurnKeyModelLink → PredictionRecord.
  * ``LoadoutService`` — build/refresh weekly load-out sheets and post actuals.
  * ``DashboardService`` — KPIs, AR collections queue, slow-movers.

Views stay thin; all orchestration lives here.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ERP_DATA_SOURCE_NAME = 'Healthy ERP (Azure PostgreSQL)'

# ── Declarative domain registry (§8.3) ───────────────────────────────────────

MODULES = [
    {'name': 'healthy-sales', 'description': 'Sales transactions, customers, items'},
    {'name': 'healthy-returns', 'description': 'Returns panel, load-out forecasting'},
    {'name': 'healthy-inventory', 'description': 'Stock positions, item movements'},
    {'name': 'healthy-collections', 'description': 'AR aging, customer balances'},
    {'name': 'healthy-production', 'description': 'Work orders, BOM, production cost'},
]

PIPELINES = {
    'returns': {
        'name': 'Returns / Load-Out Demand',
        'dataset_slug': 'healthy-returns-panel',
        'module': 'healthy-returns',
        'source_view': 'readable.invoice_lines',
        'turnkey_model_id': 'healthy-returns',
        'turnkey_model_name': 'Returns Load-Out Demand',
        'purpose': 'inference',
        'contract': {'min_completeness': 0.95, 'min_validity': 0.90, 'freshness_hours': 168},
    },
    'churn': {
        'name': 'Customer Churn / Rep Retention',
        'dataset_slug': 'healthy-churn-panel',
        'module': 'healthy-sales',
        'source_view': 'readable.salesman_performance',
        'turnkey_model_id': 'healthy-churn',
        'turnkey_model_name': 'Rep Churn',
        'purpose': 'training',
        'contract': {'min_completeness': 0.95, 'min_validity': 0.90, 'freshness_hours': 168},
    },
    'sales-lines': {
        'name': 'Demand Forecast / Dead-Stock',
        'dataset_slug': 'healthy-sales-lines',
        'module': 'healthy-inventory',
        'source_view': 'readable.items',
        'turnkey_model_id': 'healthy-sales-forecast',
        'turnkey_model_name': 'Demand Forecast',
        'purpose': 'training',
        'contract': {'min_completeness': 0.95, 'freshness_hours': 168},
    },
    'ar-aging': {
        'name': 'AR Collections Prioritization',
        'dataset_slug': 'healthy-ar-aging',
        'module': 'healthy-collections',
        'source_view': 'readable.customer_aging',
        'turnkey_model_id': 'healthy-ar-aging',
        'turnkey_model_name': 'AR Collections',
        'purpose': 'training',
        'contract': {'min_completeness': 0.95, 'freshness_hours': 48},
    },
    'transaction-classifier': {
        'name': 'Transaction-Type Classifier (DQ guard)',
        'dataset_slug': 'healthy-transaction-classifier-panel',
        'module': 'healthy-sales',
        'source_view': 'readable.invoice_lines',
        'turnkey_model_id': 'healthy-transaction-classifier',
        'turnkey_model_name': 'Transaction Classifier',
        'purpose': 'inference',
        'contract': {'min_completeness': 1.0, 'min_validity': 0.98},
    },
}

# Recorded ERP snapshots (dev/tests). Keys match ``source_view``. In production
# these are replaced by live read-only SELECTs against the Azure PostgreSQL ERP.
RECORDED_SNAPSHOTS = {
    'readable.invoice_lines': [
        {'invoice_id': 'INV-1001', 'item_code': 'SKU-101', 'rep_code': 'R-1042',
         'qty': 12, 'unit_price': 45.5, 'transaction_type': 'sale', 'invoice_date': '2026-08-17'},
        {'invoice_id': 'INV-1002', 'item_code': 'SKU-203', 'rep_code': 'R-1042',
         'qty': 3, 'unit_price': 120.0, 'transaction_type': 'return', 'invoice_date': '2026-08-18'},
        {'invoice_id': 'INV-1003', 'item_code': 'SKU-307', 'rep_code': 'R-1055',
         'qty': 40, 'unit_price': 18.75, 'transaction_type': 'sale', 'invoice_date': '2026-08-19'},
    ],
    'readable.salesman_performance': [
        {'rep_code': 'R-1042', 'active_customers': 84, 'visits': 71, 'orders': 63,
         'avg_order_value': 1820.0, 'returns_ratio': 0.06, 'week_start': '2026-08-17'},
        {'rep_code': 'R-1055', 'active_customers': 57, 'visits': 40, 'orders': 31,
         'avg_order_value': 1410.0, 'returns_ratio': 0.11, 'week_start': '2026-08-17'},
    ],
    'readable.items': [
        {'item_code': 'SKU-101', 'item_name': 'Fresh Tomatoes 1kg', 'movement_30d': 210,
         'stock_on_hand': 95, 'shelf_life_days': 4, 'category': 'produce'},
        {'item_code': 'SKU-203', 'item_name': 'Labneh 500g', 'movement_30d': 0,
         'stock_on_hand': 220, 'shelf_life_days': 21, 'category': 'dairy'},
        {'item_code': 'SKU-307', 'item_name': 'Eggs Tray (30)', 'movement_30d': 340,
         'stock_on_hand': 60, 'shelf_life_days': 14, 'category': 'dairy'},
    ],
    'readable.customer_aging': [
        {'customer_code': 'CUST-9001', 'rep_code': 'R-1042', 'days_overdue': 52,
         'amount_overdue': 18400.0, 'bucket': '31-60'},
        {'customer_code': 'CUST-9007', 'rep_code': 'R-1055', 'days_overdue': 95,
         'amount_overdue': 6750.0, 'bucket': '90+'},
        {'customer_code': 'CUST-9014', 'rep_code': 'R-1042', 'days_overdue': 12,
         'amount_overdue': 3100.0, 'bucket': '1-30'},
    ],
}


def _authenticated_user(user):
    """Normalize to a persisted user instance, or None for anonymous/None."""
    if user and getattr(user, 'is_authenticated', False):
        return user
    return None


# ── ERP extract ──────────────────────────────────────────────────────────────

class ERPSnapshotService:
    """Read-only extract from the Healthy ERP behind the DataSource seam."""

    data_source_name = ERP_DATA_SOURCE_NAME

    def get_data_source(self):
        """Find-or-create the read-only ERP DataSource (never overwrites creds)."""
        from connections.models import DataSource
        ds, _created = DataSource.objects.get_or_create(
            name=self.data_source_name,
            defaults={
                'source_type': 'database',
                'description': 'Read-only connection to healthy_legacy_2026 (Azure PostgreSQL).',
                'connection_config': {
                    'host': getattr(settings, 'HEALTHY_ERP_DB_HOST', ''),
                    'port': getattr(settings, 'HEALTHY_ERP_DB_PORT', 5432),
                    'database': getattr(settings, 'HEALTHY_ERP_DB_NAME', 'healthy_legacy_2026'),
                    'user': getattr(settings, 'HEALTHY_ERP_DB_USER', ''),
                },
            },
        )
        return ds

    def use_snapshot(self) -> bool:
        return bool(getattr(settings, 'HEALTHY_ERP_USE_SNAPSHOT', True))

    def extract_rows(self, source_view: str, extract_params=None) -> list[dict]:
        """Return rows for a source view. Recorded snapshot in dev/tests."""
        if self.use_snapshot():
            rows = RECORDED_SNAPSHOTS.get(source_view, [])
            return [dict(r) for r in rows]
        return self._live_extract(source_view, extract_params)

    def _live_extract(self, source_view: str, extract_params=None) -> list[dict]:
        """Read-only SELECT against the Azure ERP. NEVER writes or runs DDL.

        Guarded behind ``HEALTHY_ERP_USE_SNAPSHOT=False`` so it only runs when a
        live ERP is actually reachable. Raises a clear error if it is not.
        """
        import psycopg2
        ds = self.get_data_source()
        cfg = ds.connection_config or {}
        limit = int((extract_params or {}).get('limit', 10000))
        # Whitelist view identifiers to prevent SQL injection through the seam.
        if not source_view or not source_view.replace('.', '_').replace('_', '').isalnum():
            raise ValueError(f'Invalid ERP source view: {source_view!r}')
        conn = psycopg2.connect(
            host=cfg.get('host') or getattr(settings, 'HEALTHY_ERP_DB_HOST', ''),
            port=cfg.get('port', 5432),
            dbname=cfg.get('database') or getattr(settings, 'HEALTHY_ERP_DB_NAME', ''),
            user=cfg.get('user') or getattr(settings, 'HEALTHY_ERP_DB_USER', ''),
            password=getattr(settings, 'HEALTHY_ERP_DB_PASSWORD', ''),
        )
        try:
            conn.set_session(readonly=True, autocommit=True)
            cur = conn.cursor()
            cur.execute(
                f'SELECT * FROM {source_view} LIMIT %s', (limit,),
            )
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            cur.close()
            return rows
        finally:
            conn.close()

    def run_snapshot(self, source_view: str, *, user=None, dataset=None,
                     extract_params=None, auto_approve=False):
        """Record an ERPSnapshot and (optionally) ingest it into a DatasetVersion."""
        from .models import ERPSnapshot
        snapshot = ERPSnapshot.objects.create(
            source_view=source_view,
            extract_params=extract_params or {},
            data_source=self.get_data_source(),
            status='running',
            triggered_by=_authenticated_user(user),
        )
        try:
            rows = self.extract_rows(source_view, extract_params)
            version = None
            if dataset is not None:
                version = self._ingest(dataset, rows, user, auto_approve)
            snapshot.row_count = len(rows)
            snapshot.status = 'done'
            snapshot.completed_at = timezone.now()
            if version is not None:
                snapshot.dataset_version_id = version.id
            snapshot.save(update_fields=['row_count', 'status', 'completed_at',
                                         'dataset_version_id'])
        except Exception as exc:  # pragma: no cover — defensive audit path
            snapshot.status = 'failed'
            snapshot.error_detail = str(exc)[:2000]
            snapshot.completed_at = timezone.now()
            snapshot.save(update_fields=['status', 'error_detail', 'completed_at'])
            logger.exception('ERP snapshot failed for %s', source_view)
            raise
        return snapshot, version

    def _ingest(self, dataset, rows, user, auto_approve):
        from catalog.dataset_ingest import ingest_erp
        return ingest_erp(
            dataset, rows,
            source_ref=self.data_source_name,
            user=user,
            auto_approve=auto_approve,
        )


# ── Pipeline orchestration ───────────────────────────────────────────────────

class HealthyPipelineService:
    """Runs the 5 healthy pipelines end-to-end."""

    def ensure_dataset(self, spec, user=None):
        """Find-or-create the Module + Dataset + DataContract for a pipeline."""
        from catalog.models import DataContract, Dataset
        from core.models import Module
        module, _ = Module.objects.get_or_create(
            name=spec['module'],
            defaults={'description': dict(
                (m['name'], m['description']) for m in MODULES
            ).get(spec['module'], spec['module'])},
        )
        dataset, _ = Dataset.objects.get_or_create(
            slug=spec['dataset_slug'],
            defaults={
                'name': spec['name'],
                'module': module,
                'description': f'Healthy pipeline: {spec["name"]}',
                'created_by': _authenticated_user(user),
            },
        )
        contract = spec.get('contract') or {}
        DataContract.objects.get_or_create(
            dataset=dataset,
            defaults={
                'required_fields': spec.get('required_fields', []),
                'min_completeness': contract.get('min_completeness'),
                'min_validity': contract.get('min_validity'),
                'freshness_hours': contract.get('freshness_hours'),
                'consumer_apps': ['healthy'],
                'created_by': _authenticated_user(user),
            },
        )
        return dataset, module

    def ensure_turnkey_config(self, user=None):
        from integrations.turnkey.models import TurnKeyConfig
        config, _ = TurnKeyConfig.objects.get_or_create(
            name='TurnKey Healthy',
            defaults={
                'base_url': getattr(settings, 'TURNKEY_BASE_URL', 'https://turnkey.clearturn.tech'),
                'is_active': True,
                'created_by': _authenticated_user(user),
            },
        )
        return config

    def run_pipeline(self, pipeline_key: str, *, user=None, auto_approve=False) -> dict:
        """snapshot → DatasetVersion (DQ) → TurnKeyModelLink → PredictionRecord."""
        from integrations.turnkey.models import PredictionRecord, TurnKeyModelLink, input_hash_of

        if pipeline_key not in PIPELINES:
            raise ValueError(f"Unknown healthy pipeline: {pipeline_key!r}")
        spec = PIPELINES[pipeline_key]

        dataset, _module = self.ensure_dataset(spec, user)
        snapshot, version = ERPSnapshotService().run_snapshot(
            spec['source_view'], user=user, dataset=dataset, auto_approve=auto_approve,
        )

        config = self.ensure_turnkey_config(user)
        link, _ = TurnKeyModelLink.objects.get_or_create(
            dataset_version=version,
            turnkey_config=config,
            turnkey_model_id=spec['turnkey_model_id'],
            defaults={
                'turnkey_model_name': spec['turnkey_model_name'],
                'purpose': spec['purpose'],
                'status': 'registered',
                'linked_by': _authenticated_user(user),
            },
        )

        payload = self._prediction_payload(pipeline_key)
        prediction = PredictionRecord.objects.create(
            model_link=link,
            input_hash=input_hash_of(payload['input']),
            prediction=payload['prediction'],
        )
        return {
            'snapshot': snapshot,
            'version': version,
            'link': link,
            'prediction': prediction,
        }

    def _prediction_payload(self, pipeline_key: str) -> dict:
        """Deterministic mock prediction (TurnKey is external; dev uses a stub)."""
        if pipeline_key == 'returns':
            return {
                'input': {'rep_code': 'R-1042', 'week_start': '2026-08-24'},
                'prediction': {
                    'loadout_qty': {'SKU-101': 90, 'SKU-307': 120},
                    'dsd_route': 'Zone-North',
                },
            }
        if pipeline_key == 'churn':
            return {
                'input': {'rep_code': 'R-1042', 'week_start': '2026-08-17'},
                'prediction': {'churn_probability': 0.23, 'churn_risk': 'low'},
            }
        if pipeline_key == 'sales-lines':
            return {
                'input': {'item_code': 'SKU-203', 'window_days': 30},
                'prediction': {
                    'item_code': 'SKU-203',
                    'demand_forecast_4w': 0,
                    'dead_stock_flag': True,
                },
            }
        if pipeline_key == 'ar-aging':
            return {
                'input': {'customer_code': 'CUST-9007', 'as_of': '2026-08-24'},
                'prediction': {
                    'customer_code': 'CUST-9007',
                    'risk_score': 0.85,
                    'days_overdue': 95,
                    'amount_overdue': 6750.0,
                },
            }
        # transaction-classifier
        return {
            'input': {'invoice_id': 'INV-1001', 'line_text': 'sale of fresh produce'},
            'prediction': {'transaction_type': 'sale', 'confidence': 0.98},
        }


# ── Load-out sheets ──────────────────────────────────────────────────────────

class LoadoutService:
    """Build/refresh weekly load-out sheets and post actuals."""

    def generate_sheet(self, week_start, rep_code, *, rep_name='',
                       line_items=None, prediction_ref=None, user=None) -> object:
        from .models import LoadoutSheet
        sheet, _ = LoadoutSheet.objects.update_or_create(
            week_start=week_start,
            rep_code=rep_code,
            defaults={
                'rep_name': rep_name or '',
                'line_items': line_items or [],
                'prediction_ref': prediction_ref,
                'generated_by': _authenticated_user(user),
            },
        )
        return sheet

    def submit_actuals(self, sheet, actuals: dict) -> object:
        """Merge posted actual quantities into a load-out sheet's line items."""
        items = list(sheet.line_items or [])
        for item in items:
            code = item.get('item_code')
            if code is not None and code in actuals:
                item['qty_actual'] = actuals[code]
        sheet.line_items = items
        sheet.save(update_fields=['line_items'])
        return sheet


# ── Dashboards ───────────────────────────────────────────────────────────────

class DashboardService:
    """KPIs, AR collections queue, slow-movers (§8.5 dashboards)."""

    def summary(self) -> dict:
        from catalog.models import DatasetVersion
        from integrations.turnkey.models import PredictionRecord, TurnKeyModelLink
        from .models import ERPSnapshot, LoadoutSheet, RepHealthCard
        return {
            'pipelines': len(PIPELINES),
            'snapshots': ERPSnapshot.objects.count(),
            'snapshots_done': ERPSnapshot.objects.filter(status='done').count(),
            'dataset_versions': DatasetVersion.objects.count(),
            'model_links': TurnKeyModelLink.objects.count(),
            'predictions': PredictionRecord.objects.count(),
            'loadout_sheets': LoadoutSheet.objects.count(),
            'rep_health_cards': RepHealthCard.objects.count(),
        }

    def ar_queue(self) -> list[dict]:
        """AR collections queue, highest risk first (pipeline 4 predictions)."""
        from integrations.turnkey.models import PredictionRecord, TurnKeyModelLink
        links = TurnKeyModelLink.objects.filter(turnkey_model_id='healthy-ar-aging')
        rows = []
        for rec in PredictionRecord.objects.filter(model_link__in=links).order_by('-created_at'):
            pred = rec.prediction or {}
            if not isinstance(pred, dict):
                continue
            rows.append({
                'prediction_id': str(rec.id),
                'customer_code': pred.get('customer_code'),
                'risk_score': pred.get('risk_score'),
                'days_overdue': pred.get('days_overdue'),
                'amount_overdue': pred.get('amount_overdue'),
            })
        rows.sort(key=lambda r: (r['risk_score'] is None, -(r['risk_score'] or 0)))
        return rows

    def slow_movers(self) -> list[dict]:
        """Slow-movers from demand-forecast predictions flagged dead-stock."""
        from integrations.turnkey.models import PredictionRecord, TurnKeyModelLink
        links = TurnKeyModelLink.objects.filter(turnkey_model_id='healthy-sales-forecast')
        rows = []
        for rec in PredictionRecord.objects.filter(model_link__in=links).order_by('-created_at'):
            pred = rec.prediction or {}
            if not isinstance(pred, dict) or not pred.get('dead_stock_flag'):
                continue
            rows.append({
                'prediction_id': str(rec.id),
                'item_code': pred.get('item_code'),
                'demand_forecast_4w': pred.get('demand_forecast_4w'),
            })
        return rows
