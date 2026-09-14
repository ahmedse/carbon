#!/usr/bin/env python3
"""
Alamein Campus — full idempotent seed (Phase 1.4 Modules → Tables → Fields → Rows → Evidence).

Correctly maps the 15 journey-doc modules (M1..M15) to the 5 Alamein dept OrgUnits
(ids 88..92) and enters representative live activity rows + attaches the 4 evidence
PDFs. Idempotent: skips anything that already exists by unique key.

Usage:
    cd /home/ahmed/ws/carbon
    .venv/bin/python alamein-campus/seed_alamein_full.py
"""
import os
import json
import sys
import time

import requests
from dotenv import load_dotenv

BASE = os.environ.get("CARBON_API", "http://localhost:8009/carbon-api")
USERNAME = os.environ.get("CARBON_USER", "ahmed")

# Credentials come from backend/.env (gitignored) — never hardcoded in source.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env"))
PASSWORD = os.environ.get("CARBON_ADMIN_PASSWORD") or os.environ.get("CARBON_PASS")
if not PASSWORD:
    raise SystemExit("CARBON_ADMIN_PASSWORD not set — add it to backend/.env (see backend/.env.example).")

# ── Auth (with throttle retry) ─────────────────────────────────────────────
TOKEN = None
for attempt in range(6):
    r = requests.post(f"{BASE}/token/", json={"username": USERNAME, "password": PASSWORD})
    if r.status_code == 200:
        TOKEN = r.json()["access"]
        break
    if "throttl" in r.text.lower():
        print(f"  ⏳ throttled, waiting 8s ({attempt + 1})")
        time.sleep(8)
    else:
        print(f"❌ login failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)
if not TOKEN:
    print("❌ login failed after retries")
    sys.exit(1)

H = {"Authorization": f"Bearer {TOKEN}"}
JH = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
print("✅ logged in as", USERNAME)


def get_list(path):
    """Fetch a paginated (or flat) list, following `next` links to get ALL items."""
    out = []
    url = f"{BASE}{path}"
    while url:
        d = requests.get(url, headers=H).json()
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            out.extend(d.get("results", []))
            url = d.get("next")
        else:
            break
    return out


# ── Resolve OrgUnits by EXACT name (avoid the substring-ambiguity bug) ──────
orgs = get_list("/mdm/org-units/")
ORG_EXACT = {
    "medicine": "College of Medicine / كلية الطب",
    "finance": "Financial Affairs / الشؤون المادية",
    "transport": "Transportation / النقل",
    "hotels": "Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر",
    "hospital": "Educational Hospital / المستشفى التعليمي",
}
org_id = {}
for o in orgs:
    for key, name in ORG_EXACT.items():
        if o.get("name") == name:
            org_id[key] = o["id"]
print("   org ids:", org_id)

# ── 15 Modules (M1..M15) ───────────────────────────────────────────────────
MODULES = [
    ("Medicine — Diesel Generators",    "medicine",  1),
    ("Medicine — Electricity",          "medicine",  2),
    ("Finance — Electricity",           "finance",   2),
    ("Finance — Office Supplies",       "finance",   3),
    ("Finance — Medical Procurement",   "finance",   3),
    ("Transport — Fleet Fuel",          "transport", 1),
    ("Transport — Staff Travel",        "transport", 3),
    ("Hotels — Electricity",            "hotels",    2),
    ("Hotels — Chilled Water",          "hotels",    2),
    ("Hotels — Water",                  "hotels",    3),
    ("Hospital — Diesel Generators",    "hospital",  1),
    ("Hospital — Medical Gases",        "hospital",  1),
    ("Hospital — HVAC Refrigerants",    "hospital",  1),
    ("Hospital — Electricity",          "hospital",  2),
    ("Hospital — Water",                "hospital",  3),
]

existing_mods = get_list("/core/modules/")
mod_by_name = {m["name"]: m for m in existing_mods}
module_ids = {}
for name, ou_key, scope in MODULES:
    if name in mod_by_name:
        module_ids[name] = mod_by_name[name]["id"]
        continue
    oid = org_id.get(ou_key)
    if not oid:
        print(f"  ⚠️  org {ou_key} missing for {name}")
        continue
    r = requests.post(f"{BASE}/core/modules/", headers=JH,
                      json={"name": name, "description": f"Alamein {name}", "scope": scope, "org_unit": oid})
    if r.status_code == 201:
        module_ids[name] = r.json()["id"]
        print(f"✅ module {name} (id={r.json()['id']})")
    else:
        print(f"❌ module {name}: {r.status_code} {r.text[:150]}")

# ── 15 Tables (one per module) ─────────────────────────────────────────────
TABLES = [
    ("Medicine — Diesel Generators",    "med_gen_log",           "Diesel generator fuel logs — College of Medicine"),
    ("Medicine — Electricity",          "med_electricity",       "Monthly electricity — College of Medicine"),
    ("Finance — Electricity",           "finance_electricity",   "Monthly electricity — Financial Affairs"),
    ("Finance — Office Supplies",       "office_supplies",       "Paper and office supply purchases"),
    ("Finance — Medical Procurement",   "med_procurement",       "Medical procurement costs in USD"),
    ("Transport — Fleet Fuel",          "fleet_fuel_log",        "Monthly fleet fuel consumption"),
    ("Transport — Staff Travel",        "staff_travel",          "Staff air travel"),
    ("Hotels — Electricity",            "hotels_electricity",    "Monthly electricity — Student Hotels"),
    ("Hotels — Chilled Water",          "hotels_chilled_water",  "Chilled water consumption"),
    ("Hotels — Water",                  "hotels_water",          "Water consumption — Student Hotels"),
    ("Hospital — Diesel Generators",    "hospital_gen_log",      "Diesel generator fuel logs — Hospital"),
    ("Hospital — Medical Gases",        "medical_gas_log",       "Medical gas usage (N₂O)"),
    ("Hospital — HVAC Refrigerants",    "hvac_refrigerant_log",  "HVAC refrigerant (R-410A) service"),
    ("Hospital — Electricity",          "hospital_electricity",  "Monthly electricity — Educational Hospital"),
    ("Hospital — Water",                "hospital_water",        "Water consumption — Educational Hospital"),
]

existing_tables = get_list("/dataschema/tables/")
table_by_title = {t["title"]: t for t in existing_tables}
table_ids = {}
for mod_name, title, desc in TABLES:
    if title in table_by_title:
        table_ids[title] = table_by_title[title]["id"]
        continue
    mid = module_ids.get(mod_name)
    if not mid:
        continue
    r = requests.post(f"{BASE}/dataschema/tables/", headers=JH,
                      json={"title": title, "description": desc, "module": mid})
    if r.status_code == 201:
        table_ids[title] = r.json()["id"]
        print(f"✅ table {title} (id={r.json()['id']})")
    else:
        print(f"❌ table {title}: {r.status_code} {r.text[:150]}")

# ── Fields per table ───────────────────────────────────────────────────────
FIELDS = {
    "med_gen_log": [("period_month", "Period Month", "date", 1), ("generator_id", "Generator ID", "string", 1),
                    ("diesel_liters", "Diesel (L)", "number", 1), ("runtime_hours", "Runtime Hours", "number", 1),
                    ("purpose", "Purpose", "string", 0)],
    "med_electricity": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                        ("consumption_kwh", "Consumption (kWh)", "number", 1), ("meter_id", "Meter ID", "string", 0),
                        ("cost_egp", "Cost (EGP)", "number", 0)],
    "finance_electricity": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                            ("consumption_kwh", "Consumption (kWh)", "number", 1), ("meter_id", "Meter ID", "string", 0),
                            ("cost_egp", "Cost (EGP)", "number", 0)],
    "office_supplies": [("period_month", "Period Month", "date", 1), ("paper_reams", "Paper (Reams)", "number", 1),
                        ("paper_type", "Paper Type", "string", 0), ("supplier", "Supplier", "string", 0),
                        ("cost_egp", "Cost (EGP)", "number", 0)],
    "med_procurement": [("period_month", "Period Month", "date", 1), ("item_name", "Item Name", "string", 1),
                        ("category", "Category", "string", 0), ("cost_usd", "Cost (USD)", "number", 1),
                        ("supplier", "Supplier", "string", 0)],
    "fleet_fuel_log": [("period_month", "Period Month", "date", 1), ("vehicle_count", "Vehicle Count", "number", 1),
                       ("gasoline_liters", "Gasoline (L)", "number", 1), ("diesel_liters", "Diesel (L)", "number", 1),
                       ("total_cost_egp", "Total Cost (EGP)", "number", 0), ("supplier", "Supplier", "string", 0)],
    "staff_travel": [("period_month", "Period Month", "date", 1), ("staff_name", "Staff Name", "string", 1),
                     ("destination", "Destination", "string", 1), ("distance_km", "Distance (km)", "number", 1),
                     ("flight_class", "Flight Class", "string", 0), ("cost_egp", "Cost (EGP)", "number", 0)],
    "hotels_electricity": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                           ("consumption_kwh", "Consumption (kWh)", "number", 1), ("meter_id", "Meter ID", "string", 0),
                           ("cost_egp", "Cost (EGP)", "number", 0)],
    "hotels_chilled_water": [("period_month", "Period Month", "date", 1), ("meter_id", "Meter ID", "string", 1),
                             ("consumption_tr", "Consumption (TR)", "number", 1), ("building_id", "Building ID", "string", 0)],
    "hotels_water": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                     ("consumption_m3", "Consumption (m³)", "number", 1), ("meter_id", "Meter ID", "string", 0)],
    "hospital_gen_log": [("period_month", "Period Month", "date", 1), ("generator_id", "Generator ID", "string", 1),
                         ("diesel_liters", "Diesel (L)", "number", 1), ("runtime_hours", "Runtime Hours", "number", 1),
                         ("purpose", "Purpose", "string", 0)],
    "medical_gas_log": [("period_month", "Period Month", "date", 1), ("gas_type", "Gas Type", "string", 1),
                        ("quantity_kg", "Quantity (kg)", "number", 1), ("department", "Department", "string", 0),
                        ("purpose", "Purpose", "string", 0)],
    "hvac_refrigerant_log": [("period_month", "Period Month", "date", 1), ("unit_id", "Unit ID", "string", 1),
                             ("r410a_kg", "R-410A (kg)", "number", 1), ("service_type", "Service Type", "string", 0),
                             ("technician", "Technician", "string", 0)],
    "hospital_electricity": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                             ("consumption_kwh", "Consumption (kWh)", "number", 1), ("meter_id", "Meter ID", "string", 0),
                             ("cost_egp", "Cost (EGP)", "number", 0)],
    "hospital_water": [("period_month", "Period Month", "date", 1), ("building_id", "Building ID", "string", 1),
                       ("consumption_m3", "Consumption (m³)", "number", 1), ("meter_id", "Meter ID", "string", 0)],
}

existing_fields = get_list("/dataschema/fields/")
field_keys = {(f.get("data_table"), f.get("name")) for f in existing_fields}
total_fields = 0
for title, defs in FIELDS.items():
    tid = table_ids.get(title)
    if not tid:
        continue
    for fname, flabel, ftype, required in defs:
        if (tid, fname) in field_keys:
            continue
        r = requests.post(f"{BASE}/dataschema/fields/", headers=JH,
                          json={"data_table": tid, "name": fname, "label": flabel,
                                "type": ftype, "required": bool(required), "order": total_fields})
        if r.status_code == 201:
            total_fields += 1
            field_keys.add((tid, fname))
        else:
            print(f"❌ field {title}.{fname}: {r.status_code} {r.text[:150]}")
print(f"   fields created: {total_fields}")

# ── Representative activity rows (Scope 1/2/3 + evidence anchors) ──────────
ROWS = [
    ("med_gen_log", {"period_month": "2024-03-15", "generator_id": "GEN-MED-01", "diesel_liters": 850, "runtime_hours": 12, "purpose": "Backup test"}),
    ("fleet_fuel_log", {"period_month": "2024-01-31", "vehicle_count": 18, "gasoline_liters": 1850, "diesel_liters": 4200, "total_cost_egp": 78500, "supplier": "Misr Petroleum"}),
    ("hospital_electricity", {"period_month": "2024-01-01", "building_id": "HOSP-MAIN", "consumption_kwh": 125000, "meter_id": "MTR-HOSP-MAIN", "cost_egp": 35750}),
    ("med_procurement", {"period_month": "2024-03-20", "item_name": "MRI Contrast Agent", "category": "Radiology", "cost_usd": 8200, "supplier": "Siemens Health"}),
    ("med_electricity", {"period_month": "2024-03-01", "building_id": "MED-BLK-A", "consumption_kwh": 48000, "meter_id": "MTR-MED-A", "cost_egp": 13800}),
    ("hotels_water", {"period_month": "2024-03-01", "building_id": "SAKAN-01", "consumption_m3": 3200, "meter_id": "MTR-SK-01"}),
    ("medical_gas_log", {"period_month": "2024-03-01", "gas_type": "N2O", "quantity_kg": 42, "department": "Anesthesia", "purpose": "Surgical"}),
    ("staff_travel", {"period_month": "2024-03-10", "staff_name": "Dr. A. Hassan", "destination": "Riyadh", "distance_km": 2400, "flight_class": "Economy", "cost_egp": 9200}),
]

existing_rows = get_list("/dataschema/rows/")
row_keys = {(r.get("data_table"), json.dumps(r.get("values") or {}, sort_keys=True)) for r in existing_rows}
row_id_by_title = {}
total_rows = 0
for title, values in ROWS:
    tid = table_ids.get(title)
    if not tid:
        print(f"⚠️ table {title} missing, skipping row")
        continue
    if (tid, json.dumps(values, sort_keys=True)) in row_keys:
        continue
    r = requests.post(f"{BASE}/dataschema/rows/", headers=JH,
                      json={"data_table": tid, "values": values})
    if r.status_code == 201:
        total_rows += 1
        row_keys.add((tid, str(values)))
        row_id_by_title[title] = r.json()["id"]
        print(f"✅ row in {title} (id={r.json()['id']})")
    else:
        print(f"❌ row {title}: {r.status_code} {r.text[:200]}")
print(f"   rows created: {total_rows}")


def row_id_for(title):
    """Return a row id for a table, preferring newly-created rows then first row by table filter."""
    if title in row_id_by_title:
        return row_id_by_title[title]
    tid = table_ids.get(title)
    if not tid:
        return None
    rows = get_list(f"/dataschema/rows/?data_table={tid}")
    if rows:
        return rows[0].get("id")
    return None

# ── Attach evidence PDFs (bulk-upload endpoint) ────────────────────────────
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence")
EVIDENCE_MAP = [
    ("med_gen_log", "alamein-gen-test-report-mar2024.pdf"),
    ("fleet_fuel_log", "alamein-fuel-invoice-jan2024.pdf"),
    ("hospital_electricity", "alamein-elec-bill-hosp-jan2024.pdf"),
    ("med_procurement", "alamein-procurement-po-mar2024.pdf"),
]

existing_evidence = get_list("/evidence/")
existing_evidence_files = {e.get("original_filename") for e in existing_evidence}

total_evidence = 0
for title, fname in EVIDENCE_MAP:
    if fname in existing_evidence_files:
        print(f"⏭️  evidence {fname} already present")
        continue
    row_id = row_id_for(title)
    if not row_id:
        print(f"⚠️ no row for evidence {fname} (table {title})")
        continue
    path = os.path.join(EVIDENCE_DIR, fname)
    if not os.path.exists(path):
        print(f"⚠️ evidence file missing: {path}")
        continue
    with open(path, "rb") as fh:
        files = {"files": (fname, fh, "application/pdf")}
        data = {"data_row": str(row_id)}
        r = requests.post(f"{BASE}/evidence/bulk-upload/", headers={"Authorization": f"Bearer {TOKEN}"},
                          data=data, files=files)
        if r.status_code in (200, 201):
            total_evidence += 1
            print(f"✅ evidence {fname} → row {row_id}")
        else:
            print(f"❌ evidence {fname}: {r.status_code} {r.text[:200]}")
print(f"   evidence attached: {total_evidence}")

print("\n🎉 Done. Modules=%d Tables=%d Fields+%d Rows+%d Evidence+%d" % (
    len(module_ids), len(table_ids), total_fields, total_rows, total_evidence))
