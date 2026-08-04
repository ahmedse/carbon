# Alamein Campus — End-to-End Test Journey

**Purpose**: Manually build a complete Alamein Campus carbon data trust from scratch.  
**Operator**: You (admin). Assisted by role-scoped users.  
**Prerequisites**: Django backend running on port 8009, React frontend on port 5179.  
**Admin Credentials**: `ahmed` / `AdminPa_132`

---

## CAMPUS OVERVIEW

| Alamein Campus | العَلَمين |
|---|---|
| Type | University campus (sister to Abu Qir & Alexandria) |
| Departments | 5 (Medicine, Financial Affairs, Transport, Student Hotels, Educational Hospital) |
| Scopes | All 3 — direct fuel/gas (S1), grid electricity/cooling (S2), procurement/water/flights (S3) |

## ORG TREE

```
AAST (root, already exists)
└── Alamein Campus (NEW)
    ├── College of Medicine / كلية الطب (NEW)
    ├── Financial Affairs / الشؤون المادية (NEW)
    ├── Transportation / النقل (NEW)
    ├── Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر (NEW)
    └── Educational Hospital / المستشفى التعليمي (NEW)
```

## EMISSION SOURCES (per scope)

### Scope 1 — Direct Emissions
| # | Source | Dept | Module | Table | Activity | Unit | EF |
|---|---|---|---|---|---|---|---|
| S1-1 | Diesel backup generators | Medicine | Medicine — Diesel Generators | generator_fuel_log | diesel_liters | L | DIESEL_STATIONARY |
| S1-2 | Fleet fuel (buses) | Transport | Transport — Fleet Fuel | fleet_fuel_log | gasoline_liters, diesel_liters | L | GASOLINE_EG, DIESEL_MOBILE_EG |
| S1-3 | Diesel generators | Hospital | Hospital — Diesel Generators | hospital_gen_log | diesel_liters | L | DIESEL_STATIONARY |
| S1-4 | Medical gas (N₂O) | Hospital | Hospital — Medical Gases | medical_gas_log | n2o_kg | kg | N2O_GWP (custom) |
| S1-5 | Refrigerant leakage (R-410A) | Hospital | Hospital — HVAC | hvac_refrigerant_log | r410a_kg | kg | R410A_LEAK |

### Scope 2 — Indirect (Purchased Energy)
| # | Source | Dept | Module | Table | Activity | Unit | EF |
|---|---|---|---|---|---|---|---|
| S2-1 | Grid electricity | Medicine | Medicine — Electricity | med_electricity | consumption_kwh | kWh | EGY_GRID_2024 |
| S2-2 | Grid electricity | Financial Affairs | Finance — Electricity | finance_electricity | consumption_kwh | kWh | EGY_GRID_2024 |
| S2-3 | Grid electricity | Student Hotels | Hotels — Electricity | hotels_electricity | consumption_kwh | kWh | EGY_GRID_2024 |
| S2-4 | Grid electricity | Hospital | Hospital — Electricity | hospital_electricity | consumption_kwh | kWh | EGY_GRID_2024 |
| S2-5 | Chilled water (district cooling) | Student Hotels | Hotels — Chilled Water | hotels_chilled_water | consumption_tr | TR | CHILLED_WATER_EG |

### Scope 3 — Other Indirect
| # | Source | Dept | Module | Table | Activity | Unit | EF |
|---|---|---|---|---|---|---|---|
| S3-1 | Water consumption | Student Hotels | Hotels — Water | hotels_water | consumption_m3 | m³ | WATER_EG |
| S3-2 | Water consumption | Hospital | Hospital — Water | hospital_water | consumption_m3 | m³ | WATER_EG |
| S3-3 | Paper/office supplies | Financial Affairs | Finance — Office Supplies | office_supplies | paper_reams, cost_egp | reams | PAPER_WASTE_EG |
| S3-4 | Staff flights (conf.) | Transport | Transport — Staff Travel | staff_travel | distance_km | km | FLIGHT_SHORT_EG |
| S3-5 | Procurement — medical supplies | Financial Affairs | Finance — Medical Procurement | med_procurement | cost_usd | USD | PROCUREMENT_GEN |

## USERS & RBAC

| Username | Password | Role | Scoped Org Unit |
|---|---|---|---|
| `alamein.admin` | `Alamein_2026` | Domain Lead (Carbon) | Alamein Campus |
| `alamein.medical` | `Alamein_2026` | Data Owner | College of Medicine + Educational Hospital |
| `alamein.transport` | `Alamein_2026` | Data Owner | Transportation |
| `alamein.finance` | `Alamein_2026` | Data Owner | Financial Affairs |
| `alamein.hotels` | `Alamein_2026` | Data Owner | Student Hotels — Sakan Masr |

---

# PHASE 1 — FOUNDATION (Admin User)

> **Login as**: `ahmed` / `AdminPa_132`  
> **Tools**: Platform Admin sidebar (Users, Groups, Org Units, Audit) + Catalog Studio + Carbon Configuration pages  
> **Zero Django Admin needed** — everything is in the frontend at http://localhost:5179

## 1.1 Create the Alamein Org Unit

- [ ] Go to **Platform Admin → Org Units** (`/admin/org-units`)
- [ ] Click **Add Org Unit**
  - **Name**: `Alamein Campus`
  - **Type**: `campus`
  - **Parent**: `AAST`
  - **Code**: `ALAMEIN`
  - **Active**: ✅
- [ ] Save. Note the Alamein Campus ID: ______

## 1.2 Create Department Org Units

For each department below, go to **Platform Admin → Org Units** (`/admin/org-units`) → Add, set Parent = Alamein Campus:

- [ ] **College of Medicine**
  - Name: `College of Medicine / كلية الطب`
  - Type: `department`
  - Code: `MED`
  - Parent: Alamein Campus

- [ ] **Financial Affairs**
  - Name: `Financial Affairs / الشؤون المادية`
  - Type: `department`
  - Code: `FIN`
  - Parent: Alamein Campus

- [ ] **Transportation**
  - Name: `Transportation / النقل`
  - Type: `department`
  - Code: `ALTRANS`
  - Parent: Alamein Campus

- [ ] **Student Hotels — Sakan Masr**
  - Name: `Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر`
  - Type: `department`
  - Code: `HOTELS`
  - Parent: Alamein Campus

- [ ] **Educational Hospital**
  - Name: `Educational Hospital / المستشفى التعليمي`
  - Type: `department`
  - Code: `HOSPITAL`
  - Parent: Alamein Campus

## 1.3 Create Users

> **OPTION A — Platform Admin → Users** (`/admin/users`): Click Add User (do 5 times)  
> **OPTION B — Shell shortcut** (paste this once in terminal):

```bash
cd /home/ahmed/aast/carbon/backend && source ../.venv/bin/activate && python manage.py shell -c "
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from accounts.models import ScopedRole
from mdm.models import OrgUnit

User = get_user_model()
dataowners, _ = Group.objects.get_or_create(name='dataowners_group')
carbon_lead, _ = Group.objects.get_or_create(name='carbon_lead')

specs = [
    ('alamein.admin', 'alamein.admin@aast.edu', 'Alamein_2026', carbon_lead, None),
    ('alamein.medical', 'alamein.medical@aast.edu', 'Alamein_2026', dataowners, 'College of Medicine / كلية الطب'),
    ('alamein.finance', 'alamein.finance@aast.edu', 'Alamein_2026', dataowners, 'Financial Affairs / الشؤون المادية'),
    ('alamein.transport', 'alamein.transport@aast.edu', 'Alamein_2026', dataowners, 'Transportation / النقل'),
    ('alamein.hotels', 'alamein.hotels@aast.edu', 'Alamein_2026', dataowners, 'Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر'),
]
for username, email, password, group, ou_name in specs:
    user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'is_active': True})
    if created: user.set_password(password); user.save()
    user.groups.add(group)
    if ou_name:
        ou = OrgUnit.objects.filter(name=ou_name).first()
        if ou:
            ScopedRole.objects.get_or_create(user=user, group=group, org_unit=ou, defaults={'is_active': True})
    print(f'  {\"CREATED\" if created else \"EXISTS\"} {username}')
print('Done.')
"
```

- [ ] Users created. Verify each can log in at `/login`.

> **RBAC Test**: Log out. Log in as `alamein.transport`. Go to `/carbon/my-data`.  
> You should see ONLY the Transportation module(s). Not Medicine. Not Hotels.  
> If you see everything, the ScopedRole assignment is wrong (org unit may have a different name — check exact match with the org unit's `name` field).

## 1.4 Create Modules

> **Catalog Studio → Data Products** (`/catalog/products`) → Add Data Product

For each module below:
- **Name**: exact match from table
- **Scope**: 1, 2, or 3
- **Org Unit**: select from dropdown

| # | Module Name | Scope | Org Unit |
|---|---|---|---|
| M1 | Medicine — Diesel Generators | 1 | College of Medicine |
| M2 | Medicine — Electricity | 2 | College of Medicine |
| M3 | Finance — Electricity | 2 | Financial Affairs |
| M4 | Finance — Office Supplies | 3 | Financial Affairs |
| M5 | Finance — Medical Procurement | 3 | Financial Affairs |
| M6 | Transport — Fleet Fuel | 1 | Transportation |
| M7 | Transport — Staff Travel | 3 | Transportation |
| M8 | Hotels — Electricity | 2 | Student Hotels — Sakan Masr |
| M9 | Hotels — Chilled Water | 2 | Student Hotels — Sakan Masr |
| M10 | Hotels — Water | 3 | Student Hotels — Sakan Masr |
| M11 | Hospital — Diesel Generators | 1 | Educational Hospital |
| M12 | Hospital — Medical Gases | 1 | Educational Hospital |
| M13 | Hospital — HVAC Refrigerants | 1 | Educational Hospital |
| M14 | Hospital — Electricity | 2 | Educational Hospital |
| M15 | Hospital — Water | 3 | Educational Hospital |

> **Check**: Log in as `alamein.medical`. Go to `/carbon/my-data`.  
> You should see 5 modules (M1, M2, M11, M12, M13, M14, M15).  
> Also give `alamein.medical` a second ScopedRole for Educational Hospital.

## 1.5 Create Data Tables + Fields

> **Schema Admin → Table Manager** (`/schema-admin/table-manager`) — full CRUD for tables AND fields

For each table below, click **Add Table**:
- **Module**: select the module
- **Name**: `table_name` (snake_case — used for API)
- **Title**: human-readable title
- **Description**: short description

Then in the same page, click the **Fields** button on each table row to add fields.

### M1: Medicine — Diesel Generators

| Table Name | Title | Description |
|---|---|---|
| `med_gen_log` | Medicine Generator Diesel Log | Backup diesel generator fuel logs for College of Medicine |

**Fields**:
| Name | Label | Type | Required | Order |
|---|---|---|---|---|
| `period_month` | Period Month | date | ✅ | 1 |
| `generator_id` | Generator ID | string | ✅ | 2 |
| `diesel_liters` | Diesel (L) | number | ✅ | 3 |
| `runtime_hours` | Runtime Hours | number | ✅ | 4 |
| `purpose` | Purpose | string | ❌ | 5 |

### M2: Medicine — Electricity

| Table Name | Title |
|---|---|
| `med_electricity` | Medicine Monthly Electricity (kWh) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_kwh` (number, req), `meter_id` (string), `cost_egp` (number)

### M3: Finance — Electricity

| Table Name | Title |
|---|---|
| `finance_electricity` | Finance Building Electricity (kWh) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_kwh` (number, req), `meter_id` (string), `cost_egp` (number)

### M4: Finance — Office Supplies

| Table Name | Title |
|---|---|
| `office_supplies` | Office Supplies & Paper Log |

**Fields**: `period_month` (date), `paper_reams` (number, req), `paper_type` (string), `supplier` (string), `cost_egp` (number)

### M5: Finance — Medical Procurement

| Table Name | Title |
|---|---|
| `med_procurement` | Medical Supplies Procurement (USD) |

**Fields**: `period_month` (date), `item_name` (string, req), `category` (string), `cost_usd` (number, req), `supplier` (string)

### M6: Transport — Fleet Fuel

| Table Name | Title |
|---|---|
| `fleet_fuel_log` | Alamein Fleet Fuel Consumption |

**Fields**: `period_month` (date), `vehicle_count` (number, req), `gasoline_liters` (number, req), `diesel_liters` (number, req), `total_cost_egp` (number), `supplier` (string)

### M7: Transport — Staff Travel

| Table Name | Title |
|---|---|
| `staff_travel` | Staff Conference Air Travel |

**Fields**: `period_month` (date), `staff_name` (string, req), `destination` (string, req), `distance_km` (number, req), `flight_class` (string), `cost_egp` (number)

### M8: Hotels — Electricity

| Table Name | Title |
|---|---|
| `hotels_electricity` | Student Hotels Electricity (kWh) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_kwh` (number, req), `meter_id` (string), `cost_egp` (number)

### M9: Hotels — Chilled Water

| Table Name | Title |
|---|---|
| `hotels_chilled_water` | Hotels Chilled Water (TR) |

**Fields**: `period_month` (date), `meter_id` (string, req), `consumption_tr` (number, req), `building_id` (string)

### M10: Hotels — Water

| Table Name | Title |
|---|---|
| `hotels_water` | Hotels Water Consumption (m³) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_m3` (number, req), `meter_id` (string)

### M11: Hospital — Diesel Generators

| Table Name | Title |
|---|---|
| `hospital_gen_log` | Hospital Generator Diesel Log |

**Fields**: `period_month` (date), `generator_id` (string, req), `diesel_liters` (number, req), `runtime_hours` (number, req), `purpose` (string)

### M12: Hospital — Medical Gases

| Table Name | Title |
|---|---|
| `medical_gas_log` | Hospital Medical Gas Usage |

**Fields**: `period_month` (date), `gas_type` (string, req), `quantity_kg` (number, req), `department` (string), `purpose` (string)

### M13: Hospital — HVAC Refrigerants

| Table Name | Title |
|---|---|
| `hvac_refrigerant_log` | Hospital HVAC Refrigerant Log |

**Fields**: `period_month` (date), `unit_id` (string, req), `r410a_kg` (number, req), `service_type` (string), `technician` (string)

### M14: Hospital — Electricity

| Table Name | Title |
|---|---|
| `hospital_electricity` | Hospital Electricity (kWh) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_kwh` (number, req), `meter_id` (string), `cost_egp` (number)

### M15: Hospital — Water

| Table Name | Title |
|---|---|
| `hospital_water` | Hospital Water Consumption (m³) |

**Fields**: `period_month` (date), `building_id` (string, req), `consumption_m3` (number, req), `meter_id` (string)

---

# PHASE 2 — DATA ENTRY (Role-Scoped Users)

> Now switch to each scoped user and enter real data via the frontend.  
> Navigate to `/carbon/my-data` → click the module → click a table → **Data Entry** page.

## 2.1 Login as `alamein.medical` — Medicine + Hospital

### M2: Medicine Electricity (Scope 2)

Go to `/carbon/my-data` → Medicine — Electricity → `med_electricity` → enter:

| period_month | building_id | consumption_kwh | meter_id | cost_egp |
|---|---|---|---|---|
| 2024-01-01 | MED-101 | 28500 | MTR-MED-101 | 8150 |
| 2024-02-01 | MED-101 | 26100 | MTR-MED-101 | 7460 |
| 2024-03-01 | MED-101 | 27300 | MTR-MED-101 | 7810 |
| 2024-04-01 | MED-101 | 29400 | MTR-MED-101 | 8400 |
| 2024-05-01 | MED-101 | 31200 | MTR-MED-101 | 8920 |
| 2024-06-01 | MED-101 | 33500 | MTR-MED-101 | 9580 |
| 2024-07-01 | MED-102 | 18800 | MTR-MED-102 | 5370 |
| 2024-08-01 | MED-102 | 17900 | MTR-MED-102 | 5120 |
| 2024-09-01 | MED-102 | 19200 | MTR-MED-102 | 5490 |
| 2024-10-01 | MED-102 | 20500 | MTR-MED-102 | 5860 |
| 2024-11-01 | MED-102 | 19800 | MTR-MED-102 | 5660 |
| 2024-12-01 | MED-102 | 21300 | MTR-MED-102 | 6090 |

### M1: Medicine Diesel Generators (Scope 1)

| period_month | generator_id | diesel_liters | runtime_hours | purpose |
|---|---|---|---|---|
| 2024-03-15 | GEN-MED-01 | 245 | 14 | Power outage |
| 2024-06-20 | GEN-MED-01 | 180 | 10 | Scheduled test |
| 2024-07-10 | GEN-MED-01 | 520 | 28 | Extended outage |
| 2024-09-05 | GEN-MED-01 | 195 | 11 | Maintenance test |
| 2024-11-12 | GEN-MED-02 | 310 | 18 | Grid failure |

### M14: Hospital Electricity (Scope 2)

| period_month | building_id | consumption_kwh | meter_id | cost_egp |
|---|---|---|---|---|
| 2024-01-01 | HOSP-MAIN | 125000 | MTR-HOSP-MAIN | 35750 |
| 2024-02-01 | HOSP-MAIN | 118500 | MTR-HOSP-MAIN | 33890 |
| 2024-03-01 | HOSP-MAIN | 131200 | MTR-HOSP-MAIN | 37520 |
| 2024-04-01 | HOSP-MAIN | 142800 | MTR-HOSP-MAIN | 40840 |
| 2024-05-01 | HOSP-MAIN | 156300 | MTR-HOSP-MAIN | 44700 |
| 2024-06-01 | HOSP-MAIN | 168900 | MTR-HOSP-MAIN | 48300 |
| 2024-07-01 | HOSP-WING-B | 89500 | MTR-HOSP-B | 25590 |
| 2024-08-01 | HOSP-WING-B | 92100 | MTR-HOSP-B | 26340 |
| 2024-09-01 | HOSP-WING-B | 87400 | MTR-HOSP-B | 24990 |
| 2024-10-01 | HOSP-WING-B | 93800 | MTR-HOSP-B | 26820 |
| 2024-11-01 | HOSP-WING-B | 90100 | MTR-HOSP-B | 25760 |
| 2024-12-01 | HOSP-WING-B | 95700 | MTR-HOSP-B | 27370 |

### M11: Hospital Diesel Generators (Scope 1)

| period_month | generator_id | diesel_liters | runtime_hours | purpose |
|---|---|---|---|---|
| 2024-02-08 | GEN-HOSP-A | 890 | 42 | Power outage — surgery |
| 2024-05-15 | GEN-HOSP-A | 430 | 22 | Scheduled test |
| 2024-08-22 | GEN-HOSP-B | 1120 | 55 | Extended blackout |
| 2024-10-03 | GEN-HOSP-A | 380 | 18 | Grid maintenance |
| 2024-12-18 | GEN-HOSP-B | 670 | 32 | Storm outage |

### M12: Hospital Medical Gases (Scope 1)

| period_month | gas_type | quantity_kg | department | purpose |
|---|---|---|---|---|
| 2024-01-31 | N2O | 48.5 | Surgery | Anesthesia |
| 2024-02-29 | N2O | 52.1 | Surgery | Anesthesia |
| 2024-03-31 | N2O | 46.8 | Surgery | Anesthesia |
| 2024-04-30 | N2O | 55.3 | Surgery | Anesthesia |
| 2024-05-31 | N2O | 50.7 | Surgery | Anesthesia |
| 2024-06-30 | N2O | 44.2 | Surgery | Anesthesia |

### M13: Hospital HVAC Refrigerants (Scope 1)

| period_month | unit_id | r410a_kg | service_type | technician |
|---|---|---|---|---|
| 2024-03-15 | AHU-SURG-01 | 2.8 | Recharge | Eng. Mahmoud |
| 2024-07-22 | CHILLER-MAIN | 5.1 | Leak repair + recharge | Eng. Mahmoud |
| 2024-10-10 | AHU-ICU-02 | 1.9 | Recharge | Eng. Samir |

### M15: Hospital Water (Scope 3)

| period_month | building_id | consumption_m3 | meter_id |
|---|---|---|---|
| 2024-01-01 | HOSP-MAIN | 2850 | WTR-HOSP-MAIN |
| 2024-02-01 | HOSP-MAIN | 2690 | WTR-HOSP-MAIN |
| 2024-03-01 | HOSP-MAIN | 2940 | WTR-HOSP-MAIN |
| 2024-04-01 | HOSP-MAIN | 3120 | WTR-HOSP-MAIN |
| 2024-05-01 | HOSP-MAIN | 3380 | WTR-HOSP-MAIN |
| 2024-06-01 | HOSP-MAIN | 3550 | WTR-HOSP-MAIN |

---

## 2.2 Login as `alamein.transport` — Transportation

### M6: Transport Fleet Fuel (Scope 1)

| period_month | vehicle_count | gasoline_liters | diesel_liters | total_cost_egp | supplier |
|---|---|---|---|---|---|
| 2024-01-31 | 12 | 1850 | 4200 | 78500 | Misr Petroleum |
| 2024-02-29 | 12 | 1720 | 3950 | 73500 | Misr Petroleum |
| 2024-03-31 | 12 | 1980 | 4450 | 83200 | Misr Petroleum |
| 2024-04-30 | 13 | 2050 | 4680 | 87200 | Misr Petroleum |
| 2024-05-31 | 13 | 1920 | 4380 | 81400 | Cooperation |
| 2024-06-30 | 13 | 1880 | 4250 | 79200 | Cooperation |
| 2024-07-31 | 13 | 2150 | 4890 | 91500 | Misr Petroleum |
| 2024-08-31 | 13 | 2080 | 4720 | 88200 | Misr Petroleum |
| 2024-09-30 | 13 | 1950 | 4480 | 83500 | Cooperation |
| 2024-10-31 | 14 | 2230 | 5120 | 95400 | Misr Petroleum |
| 2024-11-30 | 14 | 2100 | 4850 | 90500 | Misr Petroleum |
| 2024-12-31 | 14 | 1980 | 4580 | 85500 | Cooperation |

### M7: Transport Staff Travel (Scope 3)

| period_month | staff_name | destination | distance_km | flight_class | cost_egp |
|---|---|---|---|---|---|
| 2024-03-15 | Dr. Ahmed Samir | London | 3520 | Economy | 12450 |
| 2024-05-20 | Dr. Layla Hassan | Dubai | 2580 | Economy | 8950 |
| 2024-06-10 | Prof. Khaled Omar | Paris | 3210 | Business | 28200 |
| 2024-09-05 | Dr. Noha Ibrahim | Riyadh | 1620 | Economy | 6200 |
| 2024-11-18 | Dr. Ahmed Samir | Berlin | 2950 | Economy | 11200 |

---

## 2.3 Login as `alamein.finance` — Financial Affairs

### M3: Finance Electricity (Scope 2)

| period_month | building_id | consumption_kwh | meter_id | cost_egp |
|---|---|---|---|---|
| 2024-01-01 | FIN-TOWER | 42500 | MTR-FIN-01 | 12150 |
| 2024-02-01 | FIN-TOWER | 39800 | MTR-FIN-01 | 11380 |
| 2024-03-01 | FIN-TOWER | 41200 | MTR-FIN-01 | 11780 |
| 2024-04-01 | FIN-TOWER | 43800 | MTR-FIN-01 | 12520 |
| 2024-05-01 | FIN-TOWER | 45600 | MTR-FIN-01 | 13040 |
| 2024-06-01 | FIN-TOWER | 48200 | MTR-FIN-01 | 13780 |

### M4: Finance Office Supplies (Scope 3)

| period_month | paper_reams | paper_type | supplier | cost_egp |
|---|---|---|---|---|
| 2024-01-15 | 85 | A4 80gsm | OfficeMax Egypt | 4580 |
| 2024-02-15 | 72 | A4 80gsm | OfficeMax Egypt | 3890 |
| 2024-03-15 | 95 | A4 80gsm | Office Depot | 5120 |
| 2024-04-15 | 68 | A4 80gsm | OfficeMax Egypt | 3670 |
| 2024-05-15 | 110 | A4 80gsm | Office Depot | 5930 |
| 2024-06-15 | 78 | A4 80gsm | OfficeMax Egypt | 4210 |

### M5: Finance Medical Procurement (Scope 3)

| period_month | item_name | category | cost_usd | supplier |
|---|---|---|---|---|
| 2024-01-20 | Surgical gloves (10k) | Consumables | 2450 | MedEquip Intl |
| 2024-02-20 | MRI contrast agent | Imaging | 8200 | Siemens Health |
| 2024-03-20 | ICU ventilators x3 | Equipment | 48500 | Philips Medical |
| 2024-04-20 | Surgical sutures | Consumables | 1850 | MedEquip Intl |
| 2024-05-20 | X-ray films | Imaging | 3200 | Siemens Health |
| 2024-06-20 | Blood test reagents | Lab | 5600 | Roche Diagnostics |

---

## 2.4 Login as `alamein.hotels` — Student Hotels

### M8: Hotels Electricity (Scope 2)

| period_month | building_id | consumption_kwh | meter_id | cost_egp |
|---|---|---|---|---|
| 2024-01-01 | SAKAN-A | 18500 | MTR-SAK-A | 5290 |
| 2024-02-01 | SAKAN-A | 17200 | MTR-SAK-A | 4920 |
| 2024-03-01 | SAKAN-A | 19800 | MTR-SAK-A | 5660 |
| 2024-04-01 | SAKAN-A | 21500 | MTR-SAK-A | 6150 |
| 2024-05-01 | SAKAN-A | 23200 | MTR-SAK-A | 6630 |
| 2024-06-01 | SAKAN-A | 24800 | MTR-SAK-A | 7090 |
| 2024-01-01 | SAKAN-B | 15500 | MTR-SAK-B | 4430 |
| 2024-02-01 | SAKAN-B | 14200 | MTR-SAK-B | 4060 |
| 2024-03-01 | SAKAN-B | 16300 | MTR-SAK-B | 4660 |
| 2024-04-01 | SAKAN-B | 17800 | MTR-SAK-B | 5090 |
| 2024-05-01 | SAKAN-B | 19100 | MTR-SAK-B | 5460 |
| 2024-06-01 | SAKAN-B | 20500 | MTR-SAK-B | 5860 |

### M9: Hotels Chilled Water (Scope 2)

| period_month | meter_id | consumption_tr | building_id |
|---|---|---|---|
| 2024-01-01 | CH-SAK-A | 12500 | SAKAN-A |
| 2024-02-01 | CH-SAK-A | 11800 | SAKAN-A |
| 2024-03-01 | CH-SAK-A | 13200 | SAKAN-A |
| 2024-04-01 | CH-SAK-A | 14800 | SAKAN-A |
| 2024-05-01 | CH-SAK-A | 16500 | SAKAN-A |
| 2024-06-01 | CH-SAK-A | 18200 | SAKAN-A |

### M10: Hotels Water (Scope 3)

| period_month | building_id | consumption_m3 | meter_id |
|---|---|---|---|
| 2024-01-01 | SAKAN-A | 620 | WTR-SAK-A |
| 2024-02-01 | SAKAN-A | 585 | WTR-SAK-A |
| 2024-03-01 | SAKAN-A | 650 | WTR-SAK-A |
| 2024-04-01 | SAKAN-A | 710 | WTR-SAK-A |
| 2024-05-01 | SAKAN-A | 780 | WTR-SAK-A |
| 2024-06-01 | SAKAN-A | 840 | WTR-SAK-A |
| 2024-01-01 | SAKAN-B | 510 | WTR-SAK-B |
| 2024-02-01 | SAKAN-B | 480 | WTR-SAK-B |
| 2024-03-01 | SAKAN-B | 535 | WTR-SAK-B |
| 2024-04-01 | SAKAN-B | 590 | WTR-SAK-B |
| 2024-05-01 | SAKAN-B | 645 | WTR-SAK-B |
| 2024-06-01 | SAKAN-B | 700 | WTR-SAK-B |

---

# PHASE 3 — DATA TRUST (DQ + Evidence)

## 3.1 Upload Evidence

> For each row, click the row → right panel → **Evidence** tab → Upload

**Evidence files in `alamein-campus/evidence/`**:
| File | Attach to | Row |
|---|---|---|
| `alamein-gen-test-report-mar2024.pdf` | Medicine Gen (M1) | GEN-MED-01, Mar 2024 |
| `alamein-fuel-invoice-jan2024.pdf` | Fleet Fuel (M6) | Jan 2024 |
| `alamein-elec-bill-hosp-jan2024.pdf` | Hospital Elec (M14) | HOSP-MAIN, Jan 2024 |
| `alamein-procurement-po-mar2024.pdf` | Med Procurement (M5) | MRI contrast, Mar 2024 |

- [ ] Upload at least 1 evidence file per department
- [ ] Verify evidence appears in the Evidence tab
- [ ] Verify the Trust tab shows "N evidence documents"

## 3.2 Set Up DQ Rules

> **Catalog Studio → DQ Rules** (`/catalog/dq-rules`) → Add Rule

Create DQ rules for key tables:

- [ ] **Medicine Electricity**: `consumption_kwh` NOT NULL (error)
- [ ] **Medicine Electricity**: `consumption_kwh` range 0-50000 (warn)
- [ ] **Hospital Electricity**: `consumption_kwh` NOT NULL (error)
- [ ] **Fleet Fuel**: `gasoline_liters` NOT NULL (error)
- [ ] **Fleet Fuel**: `vehicle_count` range 1-50 (warn)
- [ ] **Hotels Water**: `consumption_m3` NOT NULL (error)
- [ ] **Hotels Water**: `consumption_m3` range 0-2000 (warn)
- [ ] **Medical Gases**: `quantity_kg` NOT NULL (error)
- [ ] **Office Supplies**: `paper_reams` range 0-500 (info)

## 3.3 Run DQ Checks

- [ ] Go to each module → Health tab
- [ ] Verify DQ score is calculated
- [ ] Verify failing rules are highlighted
- [ ] Go to a row → DQ Metrics tab → verify per-row DQ

---

# PHASE 4 — CALCULATIONS

## 4.1 Set Up Calculation Rules

> **Carbon → Configuration → Calculation Rules** (`/carbon/admin/rules`) → Add Rule

| Table | Activity Field | Emission Factor |
|---|---|---|
| `med_electricity` | `consumption_kwh` | EGY_GRID_2024 |
| `finance_electricity` | `consumption_kwh` | EGY_GRID_2024 |
| `hotels_electricity` | `consumption_kwh` | EGY_GRID_2024 |
| `hospital_electricity` | `consumption_kwh` | EGY_GRID_2024 |
| `med_gen_log` | `diesel_liters` | DIESEL_STATIONARY |
| `hospital_gen_log` | `diesel_liters` | DIESEL_STATIONARY |
| `fleet_fuel_log` | `gasoline_liters` | GASOLINE_EG |
| `hotels_chilled_water` | `consumption_tr` | CHILLED_WATER_EG |
| `hotels_water` | `consumption_m3` | WATER_EG |
| `hospital_water` | `consumption_m3` | WATER_EG |
| `office_supplies` | `paper_reams` | PAPER_WASTE_EG |
| `staff_travel` | `distance_km` | FLIGHT_SHORT_EG |
| `med_procurement` | `cost_usd` | PROCUREMENT_GEN |
| `medical_gas_log` | `quantity_kg` | N2O_GWP (create if missing) |

## 4.2 Trigger Calculations

- [ ] Go to **Carbon → Calculations** (`/carbon/calculations`) and run calculations for each module
- [ ] Verify CO₂e values appear in:
  - [ ] Row detail page — CO₂e chip
  - [ ] Right panel — Lineage tab
  - [ ] Module workspace — Impact/Health tabs

---

# PHASE 5 — GOVERNANCE & AUDIT

## 5.1 Create Governance Policies

> **Catalog Studio → Governance Policies** (`/catalog/policies`) → Add Policy

- [ ] **Scope 1 Protection**: Prevent deletion of Scope 1 modules with data
  - policy_type: `module_delete`, scope_type: `scope`, emission_scope: 1, enabled: true
- [ ] **Hospital Data Lock**: Lock Hospital modules from editing by non-owners
  - policy_type: `module_update`, scope_type: `org_unit`, org_unit: Educational Hospital

## 5.2 Create Reporting Period

> **Carbon → Reporting → Reporting Periods** (`/carbon/reporting/periods`) → Add Period

- [ ] **FY 2024 — Alamein**
  - Name: `FY 2024 — Alamein`
  - Start: 2024-01-01, End: 2024-12-31
  - Type: annual
  - Status: open

## 5.3 Verification

- [ ] Go to **Carbon → Verification** (`/carbon/verification`) and mark FY 2024 — Alamein as verified
- [ ] Check that verified data cannot be edited (governance policy test)

---

# PHASE 6 — CROSS-CUTTING VERIFICATION

## 6.1 RBAC — Cross-Org Isolation

- [ ] Login as `alamein.transport` — go to `/carbon/my-data`
  - [ ] See ONLY Transport modules (M6, M7) — NOT Medicine or Hotels
- [ ] Login as `alamein.hotels` — go to `/carbon/my-data`
  - [ ] See ONLY Hotels modules (M8, M9, M10)
- [ ] Login as `alamein.medical` — go to `/carbon/my-data`
  - [ ] See Medicine (M1, M2) + Hospital (M11-M15)
- [ ] Login as `alamein.finance`
  - [ ] See Finance modules (M3, M4, M5)
- [ ] Login as `alamein.admin`
  - [ ] See ALL 15 modules

## 6.2 Right Panel — All 4 Levels

- [ ] **L1 My Data**: Trust (DQ gauge), Impact (SBTi, consumers), Activity (all filter chips)
- [ ] **L2 Module Workspace**: Health (DQ), Lineage (up/downstream), Governance (policies), Activity
- [ ] **L3 Data Entry**: Row Context (DQ + asset), Fields+Qual (field completeness), Evidence (uploads), Calculations (EF links)
- [ ] **L4 Row Detail**: DQ Metrics (per-row rules), Lineage (calc chain), Related (FK-linked records)
- [ ] **Gear icon** on ALL 4 levels — test show/hide tabs

## 6.3 Data Entry — Full Roundtrip

- [ ] Create a new row (Add Row button on L3)
- [ ] Edit an existing row → verify changes persist
- [ ] Delete a row → verify it's gone
- [ ] Bulk Import a CSV (download template first)
- [ ] Export selected rows to CSV

## 6.4 Breadcrumbs & Navigation

- [ ] L1 → L2 → L3 → L4 breadcrumb is complete (P1-3 was fixed)
- [ ] Back button works at each level
- [ ] Browser tab title shows correct page (P0-1 was fixed)
- [ ] Direct URL navigation works: paste `/carbon/my-data/row/{tableId}/{rowId}`

## 6.5 All Tabs — All Pages

- [ ] Every tab on every page renders without errors
- [ ] No blank panels
- [ ] No "No data" when data exists (K3 fix verification)
- [ ] Tab tooltips appear on hover with descriptions

---

# PHASE 7 — BUG BASELINE (from QA audit)

> These were previously identified. Verify fix status:

- [ ] **P0-1**: L3 `useDocumentTitle("Table Data")` — check browser tab title on Data Entry
- [ ] **P1-2**: Subtitle row count matches grid ("0 rows but 48 shown") — check L2
- [ ] **P1-3**: L4 breadcrumb includes module + table names
- [ ] **P1-4**: History tab shows meaningful entries, not "Calc update —"
- [ ] **P2-1**: L1 Scope/Status dropdowns open on click

---

# DATA SUMMARY — EXPECTED COUNTS

| Metric | Count |
|---|---|
| Org Units | 6 (1 campus + 5 departments) |
| Users | 5 |
| Modules | 15 (3 S1 + 5 S2 + 5 S3 + 2 mixed) |
| Tables | 15 |
| Data Rows | ~150 |
| Evidence Files | 4+ |
| DQ Rules | 9+ |
| Calculation Rules | 14 |
| Scopes Covered | 1, 2, 3 |

---

*End of journey. Happy testing! 🚀*

