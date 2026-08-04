#!/usr/bin/env python3
"""Create 5 Data Products, 15 tables, all fields via Carbon API."""
import requests, json, sys, time

BASE = "http://localhost:8009/carbon-api"

# ── Login with retry ───────────────────────────────────────
for attempt in range(5):
    resp = requests.post(f"{BASE}/token/", json={"username": "ahmed", "password": "AdminPa_132"})
    if resp.status_code == 200:
        TOKEN = resp.json()["access"]
        break
    data = resp.json()
    if "throttled" in str(data).lower() or "Throttled" in str(data):
        print(f"  ⏳ Throttled, waiting 8s...")
        time.sleep(8)
    else:
        print(f"❌ Login failed: {resp.status_code} {resp.text[:200]}")
        sys.exit(1)
else:
    print("❌ Login failed after retries"); sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
print("✅ Logged in as ahmed")

# ── Org units ──────────────────────────────────────────────
orgs = requests.get(f"{BASE}/mdm/org-units/", headers=HEADERS).json()
def find_org(hint):
    for o in orgs:
        if hint.lower() in o["name"].lower():
            return o["id"]
    return None

# ── 5 Data Products ────────────────────────────────────────
MODULES = [
    ("Medicine Carbon", "Medicine", 1, "Electricity + diesel generators for College of Medicine"),
    ("Finance Carbon", "Logistics Affairs", 3, "Electricity, office supplies, medical procurement"),
    ("Transport Carbon", "Transportation", 1, "Fleet fuel + staff air travel"),
    ("Hotels Carbon", "Student Hotels", 2, "Electricity, chilled water, water for student hotels"),
    ("Hospital Carbon", "Educational Hospital", 1, "Electricity, generators, medical gases, HVAC, water"),
]

existing_mods = requests.get(f"{BASE}/core/modules/", headers=HEADERS).json()
# Map both by name and by id for lookup
mod_by_name = {m["name"]: m for m in existing_mods}

module_ids = {}
for name, org_hint, scope, desc in MODULES:
    if name in mod_by_name:
        mid = mod_by_name[name]["id"]
        print(f"⏭️  {name} (id={mid})")
        module_ids[name] = mid
        continue
    org_id = find_org(org_hint)
    if not org_id:
        print(f"❌ Org '{org_hint}' not found")
        continue
    r = requests.post(f"{BASE}/core/modules/", headers=HEADERS,
                      json={"name": name, "description": desc, "scope": scope, "org_unit": org_id})
    if r.status_code == 201:
        mid = r.json()["id"]
        module_ids[name] = mid
        print(f"✅ {name} (id={mid})")
    else:
        print(f"❌ {name}: {r.status_code} {r.text[:150]}")

print(f"\n   Modules: {list(module_ids.keys())}")

# ── 15 Tables ──────────────────────────────────────────────
TABLES = [
    ("Medicine Carbon", "med_electricity", "Monthly electricity — College of Medicine"),
    ("Medicine Carbon", "med_gen_log", "Diesel generator fuel logs — College of Medicine"),
    ("Finance Carbon", "finance_electricity", "Monthly electricity — Logistics Affairs"),
    ("Finance Carbon", "office_supplies", "Paper and office supply purchases"),
    ("Finance Carbon", "med_procurement", "Medical procurement costs in USD"),
    ("Transport Carbon", "fleet_fuel_log", "Monthly fleet fuel consumption"),
    ("Transport Carbon", "staff_travel", "Staff air travel"),
    ("Hotels Carbon", "hotels_electricity", "Monthly electricity — Student Hotels"),
    ("Hotels Carbon", "hotels_chilled_water", "Chilled water consumption"),
    ("Hotels Carbon", "hotels_water", "Water consumption — Student Hotels"),
    ("Hospital Carbon", "hospital_electricity", "Monthly electricity — Educational Hospital"),
    ("Hospital Carbon", "hospital_gen_log", "Diesel generator fuel logs — Hospital"),
    ("Hospital Carbon", "medical_gas_log", "Medical gas usage (N₂O for anesthesia)"),
    ("Hospital Carbon", "hvac_refrigerant_log", "HVAC refrigerant (R-410A) leak & service"),
    ("Hospital Carbon", "hospital_water", "Water consumption — Educational Hospital"),
]

tables_resp = requests.get(f"{BASE}/dataschema/tables/", headers=HEADERS)
tables_list = tables_resp.json() if isinstance(tables_resp.json(), list) else tables_resp.json().get("results", [])
table_by_title = {t["title"]: t for t in tables_list}

table_map = {}
for module_name, title, desc in TABLES:
    if title in table_by_title:
        tid = table_by_title[title]["id"]
        print(f"⏭️  {title} (id={tid})")
        table_map[title] = tid
        continue
    mid = module_ids.get(module_name)
    if not mid: continue
    r = requests.post(f"{BASE}/dataschema/tables/", headers=HEADERS,
                      json={"title": title, "description": desc, "module": mid})
    if r.status_code == 201:
        tid = r.json()["id"]
        table_map[title] = tid
        print(f"✅ {title} (id={tid})")
    else:
        print(f"❌ {title}: {r.status_code} {r.text[:150]}")

# ── Fields ─────────────────────────────────────────────────
FIELDS = {
    "med_electricity": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_kwh", "Consumption (kWh)", "number", True),
        ("meter_id", "Meter ID", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "med_gen_log": [
        ("period_month", "Period Month", "date", True),
        ("generator_id", "Generator ID", "string", True),
        ("diesel_liters", "Diesel (L)", "number", True),
        ("runtime_hours", "Runtime Hours", "number", True),
        ("purpose", "Purpose", "string", False),
    ],
    "finance_electricity": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_kwh", "Consumption (kWh)", "number", True),
        ("meter_id", "Meter ID", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "office_supplies": [
        ("period_month", "Period Month", "date", True),
        ("paper_reams", "Paper (Reams)", "number", True),
        ("paper_type", "Paper Type", "string", False),
        ("supplier", "Supplier", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "med_procurement": [
        ("period_month", "Period Month", "date", True),
        ("item_name", "Item Name", "string", True),
        ("category", "Category", "string", False),
        ("cost_usd", "Cost (USD)", "number", True),
        ("supplier", "Supplier", "string", False),
    ],
    "fleet_fuel_log": [
        ("period_month", "Period Month", "date", True),
        ("vehicle_count", "Vehicle Count", "number", True),
        ("gasoline_liters", "Gasoline (L)", "number", True),
        ("diesel_liters", "Diesel (L)", "number", True),
        ("total_cost_egp", "Total Cost (EGP)", "number", False),
        ("supplier", "Supplier", "string", False),
    ],
    "staff_travel": [
        ("period_month", "Period Month", "date", True),
        ("staff_name", "Staff Name", "string", True),
        ("destination", "Destination", "string", True),
        ("distance_km", "Distance (km)", "number", True),
        ("flight_class", "Flight Class", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "hotels_electricity": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_kwh", "Consumption (kWh)", "number", True),
        ("meter_id", "Meter ID", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "hotels_chilled_water": [
        ("period_month", "Period Month", "date", True),
        ("meter_id", "Meter ID", "string", True),
        ("consumption_tr", "Consumption (TR)", "number", True),
        ("building_id", "Building ID", "string", False),
    ],
    "hotels_water": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_m3", "Consumption (m³)", "number", True),
        ("meter_id", "Meter ID", "string", False),
    ],
    "hospital_electricity": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_kwh", "Consumption (kWh)", "number", True),
        ("meter_id", "Meter ID", "string", False),
        ("cost_egp", "Cost (EGP)", "number", False),
    ],
    "hospital_gen_log": [
        ("period_month", "Period Month", "date", True),
        ("generator_id", "Generator ID", "string", True),
        ("diesel_liters", "Diesel (L)", "number", True),
        ("runtime_hours", "Runtime Hours", "number", True),
        ("purpose", "Purpose", "string", False),
    ],
    "medical_gas_log": [
        ("period_month", "Period Month", "date", True),
        ("gas_type", "Gas Type", "string", True),
        ("quantity_kg", "Quantity (kg)", "number", True),
        ("department", "Department", "string", False),
        ("purpose", "Purpose", "string", False),
    ],
    "hvac_refrigerant_log": [
        ("period_month", "Period Month", "date", True),
        ("unit_id", "Unit ID", "string", True),
        ("r410a_kg", "R-410A (kg)", "number", True),
        ("service_type", "Service Type", "string", False),
        ("technician", "Technician", "string", False),
    ],
    "hospital_water": [
        ("period_month", "Period Month", "date", True),
        ("building_id", "Building ID", "string", True),
        ("consumption_m3", "Consumption (m³)", "number", True),
        ("meter_id", "Meter ID", "string", False),
    ],
}

print()
total_created = 0
for table_title, field_defs in FIELDS.items():
    tid = table_map.get(table_title)
    if not tid:
        print(f"  ⚠️  Table '{table_title}' not in map, skipping")
        continue

    # Fields are at /dataschema/fields/?table={id} (flat list, not nested)
    fields_resp = requests.get(f"{BASE}/dataschema/fields/", headers=HEADERS, params={"table": tid})
    try:
        existing = fields_resp.json()
        existing_list = existing if isinstance(existing, list) else existing.get("results", [])
        existing_names = {f.get("name") or f.get("field_name", "") for f in existing_list}
    except:
        existing_names = set()

    created = 0
    for fname, flabel, ftype, required in field_defs:
        if fname in existing_names:
            continue
        payload = {"name": fname, "label": flabel, "data_type": ftype, "is_required": required, "table": tid}
        r = requests.post(f"{BASE}/dataschema/fields/", headers=HEADERS, json=payload)
        if r.status_code == 201:
            created += 1
            total_created += 1
        else:
            print(f"  ❌ {table_title}.{fname}: {r.status_code} {r.text[:120]}")

    if created:
        print(f"✅ {table_title}: +{created} fields")
    else:
        print(f"⏭️  {table_title}: all {len(field_defs)} fields already present")

print(f"\n🎉 Done! Modules={len(module_ids)} | Tables={len(table_map)} | Fields created={total_created}")
