# Carbon Data Trust Platform — Admin User Guide

## Overview

This guide documents admin capabilities and workflows for the Carbon Data Trust Platform. The platform supports two levels of admin access: global admins (platform-wide) and org-scoped admins (organization-specific).

---

## Admin Roles and Permissions

### Global Admin
- **Role:** `admins_group` with `org_unit=None`
- **Database:** ScopedRole with module=None, org_unit=None, group=admins_group
- **Permissions:** 
  - ✅ Full CRUD on governance (catalog/mdm/dq)
  - ✅ Full CRUD on schema (DataTable/DataField)
  - ✅ Full CRUD on data (DataRow) across ALL org units
  - ✅ View emissions calculations for all org units
- **Use Cases:** 
  - Platform configuration and setup
  - Governance management (creating domains, reference sets, DQ rules)
  - Schema design (creating tables and fields)
  - Cross-organizational reporting and administration

### Org-Scoped Admin
- **Role:** `admins_group` with specific `org_unit` (e.g., org_unit=5 for Facilities)
- **Database:** ScopedRole with module=None, org_unit=<specific>, group=admins_group
- **Permissions:** 
  - ✅ Read-only governance (catalog/mdm/dq)
  - ✅ Read-only schema (DataTable/DataField)
  - ✅ Full CRUD on data (DataRow) within org scope
  - ✅ View emissions calculations within org scope
  - ❌ Cannot modify governance (returns 403)
  - ❌ Cannot modify schema (returns 403)
  - ❌ Cannot access data outside their org scope
- **Use Cases:** 
  - Organization-level data entry and management
  - Org-specific reporting and dashboard access
  - Quality assurance within organization boundaries

---

## Authentication

### Getting JWT Token

All API access requires a JWT token. Obtain one via:

```bash
curl -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ADMIN_USERNAME","password":"PASSWORD"}'
```

**Response:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Use the `access` token in all subsequent API calls:
```bash
curl http://localhost:8009/carbon-api/[endpoint] \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Token Expiry
- **Access Token:** 15 minutes (900 seconds)
- **Refresh Token:** 7 days
- **Rate Limit:** 30 requests per 60 seconds per IP

---

## Global Admin Workflows

### Workflow 1: Create Data Domain (Governance)

**Endpoint:** `POST /carbon-api/catalog/domains/`

```bash
curl -X POST http://localhost:8009/carbon-api/catalog/domains/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Energy Management",
    "description": "All energy-related carbon metrics"
  }'
```

**Success Response (201 Created):**
```json
{
  "id": 3,
  "name": "Energy Management",
  "slug": "energy-management",
  "description": "All energy-related carbon metrics",
  "parent": null,
  "owner": null,
  "created_at": "2026-07-18T12:30:00Z"
}
```

### Workflow 2: Create Reference Set (Governance)

**Endpoint:** `POST /carbon-api/mdm/reference-sets/`

```bash
curl -X POST http://localhost:8009/carbon-api/mdm/reference-sets/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Energy Sources",
    "description": "Types of energy sources",
    "domain": 3
  }'
```

### Workflow 3: Create Data Quality Rule (Governance)

**Endpoint:** `POST /carbon-api/dq/rules/`

```bash
curl -X POST http://localhost:8009/carbon-api/dq/rules/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_type": "not_null",
    "data_table": 7,
    "data_field": 12,
    "severity": "error",
    "description": "Month field cannot be null"
  }'
```

### Workflow 4: Create Data Table (Schema)

**Endpoint:** `POST /carbon-api/dataschema/tables/`

```bash
curl -X POST http://localhost:8009/carbon-api/dataschema/tables/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Solar Energy Generation",
    "module": 5,
    "table_type": "activity",
    "description": "Monthly solar panel output in kWh"
  }'
```

**Success Response (201 Created):**
```json
{
  "id": 12,
  "title": "Solar Energy Generation",
  "module": 5,
  "module_name": "Facilities - Electricity",
  "version": 1,
  "is_archived": false,
  "created_at": "2026-07-18T12:35:00Z"
}
```

### Workflow 5: Add Field to Table (Schema)

**Endpoint:** `POST /carbon-api/dataschema/fields/`

```bash
curl -X POST http://localhost:8009/carbon-api/dataschema/fields/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_table": 12,
    "name": "total_kwh",
    "label": "Total Generation (kWh)",
    "type": "number",
    "order": 1,
    "required": true,
    "description": "Total kWh generated during period"
  }'
```

### Workflow 6: View Data Across All Organizations

**Endpoint:** `GET /carbon-api/dataschema/rows/`

```bash
# Get all data rows across all org units
curl http://localhost:8009/carbon-api/dataschema/rows/ \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Get data from specific table (all org data)
curl 'http://localhost:8009/carbon-api/dataschema/rows/?data_table=7' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Workflow 7: View Emissions Across All Organizations

**Endpoint:** `GET /carbon-api/emissions/calculations/`

```bash
curl http://localhost:8009/carbon-api/emissions/calculations/ \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Org-Scoped Admin Workflows

### Workflow 1: View Governance Resources (Read-Only)

**Endpoint:** `GET /carbon-api/catalog/domains/`

```bash
curl http://localhost:8009/carbon-api/catalog/domains/ \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN"
```

**Note:** Org-scoped admins can view but NOT create/modify governance.

### Workflow 2: Attempt to Create Domain (Will Fail)

```bash
curl -X POST http://localhost:8009/carbon-api/catalog/domains/ \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Will Fail"}'
```

**Response (403 Forbidden):**
```json
{"detail": "You do not have permission to perform this action."}
```

### Workflow 3: View Schema Resources in Scope (Read-Only)

**Endpoint:** `GET /carbon-api/dataschema/tables/`

```bash
# View tables in your org's modules (with module_id parameter)
curl 'http://localhost:8009/carbon-api/dataschema/tables/?module_id=5' \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN"
```

### Workflow 4: Manage Data Within Org Scope (CRUD)

**Endpoint:** `POST /carbon-api/dataschema/rows/`

```bash
curl -X POST http://localhost:8009/carbon-api/dataschema/rows/ \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_table": 7,
    "period": "2026-01",
    "values": {
      "month": "2026-01-01",
      "building_401_kwh": 112000,
      "building_2401_kwh": 98000,
      "total_kwh": 210000
    }
  }'
```

---

## Permission Reference Table

| Resource | Global Admin | Org-Scoped Admin | Data-Owner |
|----------|--------------|------------------|------------|
| Governance Domains | ✅ CREATE, READ, UPDATE, DELETE | ✅ READ-ONLY | ✅ READ-ONLY |
| Reference Sets | ✅ CREATE, READ, UPDATE, DELETE | ✅ READ-ONLY | ✅ READ-ONLY |
| DQ Rules | ✅ CREATE, READ, UPDATE, DELETE | ✅ READ-ONLY | ✅ READ-ONLY |
| Data Tables | ✅ CREATE, READ, UPDATE, DELETE | ✅ READ-ONLY | ✅ READ-ONLY |
| Data Fields | ✅ CREATE, READ, UPDATE, DELETE | ✅ READ-ONLY | ✅ READ-ONLY |
| Data Rows | ✅ All orgs | ✅ Org scope only | ✅ Org scope only |
| Emissions (Calculations) | ✅ All orgs | ✅ Org scope only | ✅ Org scope only |

---

## Error Handling

### 401 Unauthorized
- JWT token is missing or invalid
- **Fix:** Obtain a fresh token using your credentials

```bash
# Refresh token if expired
curl -X POST http://localhost:8009/carbon-api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"YOUR_REFRESH_TOKEN"}'
```

### 403 Forbidden
- User does not have permission for this action
- Common causes:
  - Org-scoped admin trying to write governance/schema
  - Data-owner trying to access schema
  - User trying to access out-of-scope organization data

**Check your role:**
```bash
curl http://localhost:8009/carbon-api/auth/me/ \
  -H "Authorization: Bearer $TOKEN"
```

### 429 Too Many Requests
- Rate limit exceeded (30 requests per 60 seconds)
- **Fix:** Wait 60 seconds before retry

---

## Troubleshooting

### "You do not have permission to perform this action"

1. **Verify Role:** Are you a global admin or org-scoped admin?
   ```bash
   curl http://localhost:8009/carbon-api/auth/me/ \
     -H "Authorization: Bearer $TOKEN"
   ```

2. **Check Write Permissions:** Only global admins can modify governance/schema
   - Org-scoped admins are read-only for governance and schema
   - Data-owners are read-only for governance and schema

3. **Check Org Scope:** Can you access the target organization/module?
   - Include `module_id` parameter if accessing scoped resources

### Token Expired

```bash
# Get new token
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"USERNAME","password":"PASSWORD"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")
```

### Module/Org ID Reference

```bash
# Get list of all modules
curl http://localhost:8009/carbon-api/core/modules/ \
  -H "Authorization: Bearer $TOKEN"

# Get list of all org units
curl http://localhost:8009/carbon-api/mdm/org-units/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## API Endpoints Summary

### Authentication
- `POST /carbon-api/token/` — Get JWT token
- `POST /carbon-api/token/refresh/` — Refresh expired token

### Governance (Catalog)
- `GET /carbon-api/catalog/domains/` — List domains (read-only for org-scoped)
- `POST /carbon-api/catalog/domains/` — Create domain (global admin only)
- `PATCH /carbon-api/catalog/domains/{id}/` — Update domain (global admin only)

### Reference Data (MDM)
- `GET /carbon-api/mdm/reference-sets/` — List reference sets
- `POST /carbon-api/mdm/reference-sets/` — Create reference set (global admin only)
- `GET /carbon-api/mdm/org-units/` — List organizations

### Data Quality (DQ)
- `GET /carbon-api/dq/rules/` — List DQ rules
- `POST /carbon-api/dq/rules/` — Create DQ rule (global admin only)

### Schema (DataSchema)
- `GET /carbon-api/dataschema/tables/` — List tables (read-only for org-scoped)
- `POST /carbon-api/dataschema/tables/` — Create table (global admin only)
- `GET /carbon-api/dataschema/fields/` — List fields (read-only for org-scoped)
- `POST /carbon-api/dataschema/fields/` — Create field (global admin only)
- `GET /carbon-api/dataschema/rows/` — Get data rows (org-scoped filtered)
- `POST /carbon-api/dataschema/rows/` — Create data row (org-scoped filtered)

### Emissions
- `GET /carbon-api/emissions/calculations/` — View emissions (org-scoped filtered)

---

## References

- **Permission Classes:** [backend/accounts/permissions.py](../backend/accounts/permissions.py)
- **RBAC Utilities:** [backend/accounts/rbac_utils.py](../backend/accounts/rbac_utils.py)
- **API Documentation:** [docs/api.md](./api.md)
- **Design Document:** [docs/DESIGN_ORG_ACCESS_MODEL.md](./DESIGN_ORG_ACCESS_MODEL.md)

---

**Last Updated:** 2026-07-18  
**Version:** 1.0
