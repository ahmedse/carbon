# AASTMT Carbon Deployment - Quick Start

## What This Does

Deploys a complete, production-ready Carbon emissions management system for AASTMT with:
- ✅ 7 organizational units (Facilities, Transport, Energy, etc.)
- ✅ 5 reference sets (building types, vehicle types, fuel types, etc.)
- ✅ 3 carbon modules (Scope 1, 2, 3)
- ✅ 6 data tables with full schemas
- ✅ 7 users with realistic roles and permissions
- ✅ 13+ sample data rows for January 2026

## Prerequisites

1. Backend and database running
2. Migrations applied
3. Python virtual environment activated

## Execution

### Option 1: Single Command
```bash
cd /home/ahmed/aast/carbon
source backend/venv/bin/activate
python backend/deploy_aastmt_carbon.py
```

### Option 2: Via manage.sh
```bash
./manage.sh shell < backend/deploy_aastmt_carbon.py
```

## Expected Output

```
======================================================================
AASTMT CARBON PLATFORM - COMPLETE DEPLOYMENT
======================================================================

1. Creating Organizational Units
======================================================================
✓ OrgUnit: AASTMT Smart Village Campus (created)
✓ OrgUnit: Facilities Management Department (created)
...

2. Creating Reference Sets & Values
======================================================================
✓ ReferenceSet: Building Types (created)
  → Administrative Building (ADM)
  → Academic Building (ACD)
...

[continues for all deployment steps]

7. Deployment Verification
======================================================================
✓ 7 Organizational Units
✓ 5 Reference Sets with 32 values
✓ 3 Carbon Modules (S1, S2, S3)
✓ 6 Data Tables with schemas
✓ 6 Users (excluding admin)
✓ 14 Scoped role assignments
✓ 13 Sample data rows

Estimated Emissions (January 2026):
  Scope 1: 3,094.30 kg CO2e (1118L diesel + 87L gasoline)
  Scope 2: 56,841.50 kg CO2e (107,850 kWh)
  Total: 59.94 tons CO2e

DEPLOYMENT COMPLETE
======================================================================
✓ All components deployed successfully!

======================================================================
LOGIN CREDENTIALS
======================================================================
> ⚠️ Credentials rotated 2026-08. Real passwords are NOT stored in this
> repo — set them at deploy time and rotate again before production.
ahmed             / <set-at-deploy>     (Platform Admin)
ali               / <set-at-deploy>     (Carbon Domain Admin)
fatima_facilities / <set-at-deploy>     (Facilities Data Owner)
mohammed_transport/ <set-at-deploy>     (Transport Data Owner)
sarah_analyst     / <set-at-deploy>     (Carbon Analyst)
youssef_energy    / <set-at-deploy>     (Energy Data Entry)
layla_auditor     / <set-at-deploy>     (Carbon Auditor)
======================================================================
```

## After Deployment

### 1. Login and Verify
```bash
# Login as Ali (Carbon Admin) — use the real password set at deploy time
curl -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ali","password":"<set-at-deploy>"}'

# Get user context
curl http://localhost:8009/carbon-api/accounts/me_context/ \
  -H "Authorization: Bearer <access_token>"
```

### 2. Access the Platform
- Frontend: http://localhost:5179/carbon/
- API Docs: http://localhost:8009/swagger/
- Django Admin: http://localhost:8009/admin/

### 3. Test User Roles

**ali** (Carbon Domain Admin)
- Can access all carbon modules
- Can manage carbon data
- Cannot access catalog (not a catalog admin)

**fatima_facilities** (Facilities Data Owner)
- Can manage Scope 1 & 2 data for facilities org unit
- Can view/edit fleet fuel and electricity tables
- Cannot access Scope 3 data

**mohammed_transport** (Transport Data Owner)
- Can manage Scope 1 fleet data for transport org unit
- Focused on vehicle fuel consumption
- Cannot access other scopes

**sarah_analyst** (Carbon Analyst)
- Read access to all carbon modules
- Can generate reports and dashboards
- Cannot edit data

**youssef_energy** (Energy Data Entry)
- Can enter Scope 2 electricity data
- Limited to energy utilities org unit
- Cannot access Scope 1 or 3

**layla_auditor** (Carbon Auditor)
- Read-only access to all carbon modules
- Can verify and audit data
- Cannot modify any data

## Re-running the Script

The script is idempotent - you can run it multiple times safely:
- Existing entities will be updated (not duplicated)
- New entities will be created
- Sample data may be duplicated (clear DataRow table first if needed)

To clear and re-deploy:
```bash
# Clear sample data only
python backend/manage.py shell -c "from dataschema.models import DataRow; DataRow.objects.all().delete()"

# Full clean (WARNING: removes all carbon data)
python backend/manage.py shell -c "
from dataschema.models import DataTable, DataRow
from core.models import Module
from mdm.models import OrgUnit, ReferenceSet
DataRow.objects.all().delete()
DataTable.objects.filter(code__startswith='S').delete()
Module.objects.filter(code__startswith='CARBON-').delete()
OrgUnit.objects.filter(code__startswith=('AASTMT', 'FAC', 'TRANS', 'ENERGY', 'PROCURE', 'IT', 'RES')).delete()
ReferenceSet.objects.filter(code__in=['BLDG_TYPE', 'VEH_TYPE', 'FUEL_TYPE', 'ENERGY_SRC', 'EMIS_CAT']).delete()
"

# Then re-run deployment
python backend/deploy_aastmt_carbon.py
```

## Next Steps

1. **Configure DQ Rules** - Add data quality rules for completeness, validity
2. **Set up Dashboards** - Create carbon owner and analyst dashboards
3. **Historical Data** - Load 2024-2025 data for trend analysis
4. **Monthly Reporting** - Configure automated emission reports
5. **Train Users** - Onboard data owners and analysts
6. **Expand Scope 3** - Add procurement, waste, water consumption
7. **Mobile App** - Enable mobile data entry for field readings

## Troubleshooting

### "Migration not applied"
```bash
cd backend && source venv/bin/activate
python manage.py migrate
```

### "Permission denied"
```bash
chmod +x backend/deploy_aastmt_carbon.py
```

### "Database connection error"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start if needed
sudo systemctl start postgresql
```

### "Import errors"
```bash
# Ensure virtual environment is activated
source backend/venv/bin/activate

# Install missing dependencies
pip install -r backend/requirements.txt
```

## Documentation

- Full deployment plan: `DEPLOYMENT_PLAN_AASTMT_CARBON.md`
- RBAC guide: `docs/ADMIN_USER_GUIDE.md`
- API docs: http://localhost:8009/swagger/

## Contact

For questions or issues, contact the platform administrator.
