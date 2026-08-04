#!/usr/bin/env python3
"""Delete all existing fields, then create correct fields per table via Carbon API."""
import requests, sys, time

BASE = "http://localhost:8009/carbon-api"

for attempt in range(5):
    resp = requests.post(f"{BASE}/token/", json={"username": "ahmed", "password": "AdminPa_132"})
    if resp.status_code == 200:
        TOKEN = resp.json()["access"]
        break
    if "throttled" in str(resp.json()).lower():
        time.sleep(8)
else:
    print("❌ Login failed"); sys.exit(1)

H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Step 1: Wipe all existing fields ───────────────────────
print("🧹 Deleting all existing fields...")
fields_resp = requests.get(f"{BASE}/dataschema/fields/", headers=H)
all_fields = fields_resp.json() if isinstance(fields_resp.json(), list) else fields_resp.json().get("results", [])
print(f"   Found {len(all_fields)} fields")

deleted = 0
for f in all_fields:
    fid = f["id"]
    r = requests.delete(f"{BASE}/dataschema/fields/{fid}/", headers=H)
    if r.status_code in (204, 200):
        deleted += 1
    else:
        print(f"   ⚠️  Could not delete field {fid}: {r.status_code}")
print(f"   Deleted {deleted} fields")

# ── Step 2: Get tables ─────────────────────────────────────
tables = requests.get(f"{BASE}/dataschema/tables/", headers=H).json()
tbl = tables if isinstance(tables, list) else tables.get("results", [])
title_to_id = {t["title"]: t["id"] for t in tbl}
print(f"\n   Tables: {list(title_to_id.keys())}")

# ── Step 3: Create fields ──────────────────────────────────
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

total = 0
print()
for table_title, field_defs in FIELDS.items():
    tid = title_to_id.get(table_title)
    if not tid:
        print(f"⚠️  '{table_title}' not found")
        continue

    created = 0
    for fname, flabel, ftype, required in field_defs:
        payload = {
            "name": fname,
            "label": flabel,
            "type": ftype,
            "required": required,
            "data_table": tid,
        }
        r = requests.post(f"{BASE}/dataschema/fields/", headers=H, json=payload)
        if r.status_code == 201:
            created += 1; total += 1
        else:
            print(f"  ❌ {table_title}.{fname}: {r.status_code} {r.text[:150]}")

    if created:
        print(f"✅ {table_title}: +{created}/{len(field_defs)} fields")

print(f"\n🎉 Done. Fields created: {total}")
