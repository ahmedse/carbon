#!/usr/bin/env python3
"""
Carbon Data Trust Core — Comprehensive Seed Script.
Creates: Domains → Tags → Glossary → Asset Profiles → DQ Rules →
         Governance Policies → Reference Sets → Table/Module metadata
NO rows, NO emission factors, NO calculation rules.
"""
import requests, sys, time, os

BASE = os.environ.get("CARBON_API", "http://localhost:8009/carbon-api")
USERNAME = os.environ.get("CARBON_USER", "ahmed")
PASSWORD = os.environ.get("CARBON_PASS", "AdminPa_132")

# ── Auth ────────────────────────────────────────────────────
for attempt in range(5):
    resp = requests.post(f"{BASE}/token/", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code == 200:
        TOKEN = resp.json()["access"]
        break
    if "throttled" in str(resp.json()).lower():
        time.sleep(8)
else:
    print("❌ Login failed"); sys.exit(1)

H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
created = {"domains": 0, "tags": 0, "glossary": 0, "assets": 0, "dq_rules": 0,
           "policies": 0, "ref_sets": 0, "ref_values": 0, "updated": 0}
skipped = 0

def post(path, payload):
    """POST with dup detection."""
    global skipped
    r = requests.post(f"{BASE}{path}", headers=H, json=payload)
    if r.status_code in (201, 200, 202):
        return r.json()
    # Check if already exists error
    status = r.status_code
    text = r.text.lower()
    if status == 400 and any(w in text for w in ["already", "unique", "exists", "duplicate"]):
        skipped += 1
        return None
    print(f"  ❌ POST {path}: {status} {r.text[:200]}")
    return None

def patch(path, payload):
    r = requests.patch(f"{BASE}{path}", headers=H, json=payload)
    return r.status_code in (200, 202)

def get(path):
    r = requests.get(f"{BASE}{path}", headers=H)
    if r.status_code == 200:
        return r.json()
    return None

def get_list(path):
    data = get(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("results", [])
    return []

# ── 1. Fetch existing data ──────────────────────────────────
print("📡 Loading current state...")
tables = get_list("/dataschema/tables/")
modules = get_list("/core/modules/")
fields = get_list("/dataschema/fields/")
existing_assets = get_list("/catalog/assets/")
existing_rules = get_list("/dq/rules/")
existing_policies = get_list("/catalog/governance-policies/")
existing_domains = get_list("/catalog/domains/")
existing_tags = get_list("/catalog/tags/")
existing_glossary = get_list("/catalog/glossary/")
existing_refsets = get_list("/mdm/reference-sets/")

table_map = {t["title"]: t for t in tables}
table_id_map = {t["id"]: t for t in tables}
field_map = {}  # table_id → [fields]
for f in fields:
    tid = f.get("data_table")
    if tid:
        field_map.setdefault(tid, []).append(f)

module_map = {m["id"]: m for m in modules}

# Tables by module
tables_by_module = {}
for t in tables:
    mid = t.get("module")
    if mid:
        tables_by_module.setdefault(mid, []).append(t)

# Asset check
existing_table_asset_ids = set()
for a in existing_assets:
    if a.get("data_table"):
        existing_table_asset_ids.add(a["data_table"])

# Domain/tag/glossary check
domain_names = {d["name"] for d in existing_domains}
tag_names = {t["name"] for t in existing_tags}
glossary_terms = {g["term"] for g in existing_glossary}

print(f"   {len(tables)} tables, {len(modules)} modules, {len(fields)} fields")
print(f"   Existing: {len(existing_assets)} assets, {len(existing_rules)} DQ rules, "
      f"{len(existing_policies)} policies, {len(existing_domains)} domains")

# ── 2. Data Domains ─────────────────────────────────────────
print("\n🏛️  Data Domains...")
DOMAINS = [
    {"name": "Medicine Carbon", "slug": "medicine-carbon",
     "description": "Carbon footprint data for the College of Medicine — electricity, generators, medical gases, HVAC, and water consumption"},
    {"name": "Logistics Carbon", "slug": "logistics-carbon",
     "description": "Carbon footprint data for Logistics Affairs — electricity, office supplies, and medical procurement"},
    {"name": "Transport Carbon", "slug": "transport-carbon",
     "description": "Carbon footprint data for Transportation — fleet fuel logs and staff travel records"},
    {"name": "Hotels Carbon", "slug": "hotels-carbon",
     "description": "Carbon footprint data for Hotels — electricity, chilled water, and water consumption"},
    {"name": "Hospital Carbon", "slug": "hospital-carbon",
     "description": "Carbon footprint data for the Hospital — electricity, generators, medical gases, HVAC refrigerants, and water"},
]
for d in DOMAINS:
    if d["name"] not in domain_names:
        post("/catalog/domains/", d)
        created["domains"] += 1

# ── 3. Tags ─────────────────────────────────────────────────
print("🏷️  Tags...")
TAGS = [
    {"name": "carbon-footprint", "slug": "carbon-footprint", "color": "#2e7d32"},
    {"name": "scope-1", "slug": "scope-1", "color": "#d32f2f"},
    {"name": "scope-2", "slug": "scope-2", "color": "#ed6c02"},
    {"name": "energy", "slug": "energy", "color": "#ff9800"},
    {"name": "transport", "slug": "transport", "color": "#1976d2"},
    {"name": "refrigerant", "slug": "refrigerant", "color": "#9c27b0"},
    {"name": "procurement", "slug": "procurement", "color": "#795548"},
    {"name": "water", "slug": "water", "color": "#0288d1"},
    {"name": "electricity", "slug": "electricity", "color": "#fdd835"},
    {"name": "fuel", "slug": "fuel", "color": "#bf360c"},
    {"name": "medical", "slug": "medical", "color": "#e91e63"},
    {"name": "aastmt", "slug": "aastmt", "color": "#1565c0"},
    {"name": "alamein", "slug": "alamein", "color": "#00897b"},
    {"name": "pii-sensitive", "slug": "pii-sensitive", "color": "#c62828"},
    {"name": "monthly", "slug": "monthly", "color": "#607d8b"},
]
for t in TAGS:
    if t["name"] not in tag_names:
        post("/catalog/tags/", t)
        created["tags"] += 1

# ── 4. Glossary Terms ───────────────────────────────────────
print("📖 Glossary Terms...")
GLOSSARY = [
    {"term": "Scope 1", "definition": "Direct GHG emissions from owned or controlled sources (fuel combustion, company vehicles, refrigerant leakage)", "status": "approved"},
    {"term": "Scope 2", "definition": "Indirect GHG emissions from the generation of purchased electricity, steam, heating, and cooling", "status": "approved"},
    {"term": "Scope 3", "definition": "All other indirect emissions in a company's value chain (procurement, business travel, waste)", "status": "approved"},
    {"term": "CO₂ equivalent", "definition": "Universal unit of measurement to indicate the global warming potential of GHGs, expressed as CO₂e", "status": "approved"},
    {"term": "Emission Factor", "definition": "A coefficient that quantifies the emissions per unit of activity (e.g., kg CO₂ per kWh)", "status": "approved"},
    {"term": "R-410A", "definition": "A hydrofluorocarbon (HFC) refrigerant blend with high global warming potential (GWP 2088)", "status": "approved"},
    {"term": "kWh", "definition": "Kilowatt-hour — standard unit of electrical energy consumption", "status": "approved"},
    {"term": "TR", "definition": "Ton of Refrigeration — a unit of cooling capacity (1 TR ≈ 3.517 kW)", "status": "approved"},
    {"term": "Chilled Water", "definition": "Water cooled to ~4-7°C used for central air conditioning in large buildings", "status": "approved"},
    {"term": "Medical Gas", "definition": "Gases used in healthcare settings (oxygen, nitrous oxide, medical air, anesthesia gases)", "status": "approved"},
    {"term": "Data Trust Core", "definition": "The governance, quality, and metadata layer of the Carbon Platform ensuring data integrity and lineage", "status": "approved"},
    {"term": "Asset Profile", "definition": "Catalog metadata record for a data table or field including classification, ownership, and quality status", "status": "approved"},
    {"term": "DQ Rule", "definition": "A data quality validation rule (not-null, unique, range, regex, or reference integrity)", "status": "approved"},
    {"term": "Governance Policy", "definition": "A configurable policy that controls whether delete/update actions are permitted on modules or tables", "status": "approved"},
    {"term": "Reference Set", "definition": "A curated set of allowed reference values (e.g., building codes, gas types) used for data validation", "status": "approved"},
]
for g in GLOSSARY:
    if g["term"] not in glossary_terms:
        post("/catalog/glossary/", g)
        created["glossary"] += 1

# ── 5. Asset Profiles (one per table) ───────────────────────
print("\n📋 Asset Profiles...")
ASSET_DEFS = {
    "med_electricity": {
        "description": "Monthly electricity consumption for College of Medicine buildings. Records kWh usage and cost per meter.",
        "classification": "internal",
        "semantic_type": "energy_consumption",
        "tags": ["electricity", "scope-2", "medical", "monthly", "aastmt", "alamein"],
    },
    "med_gen_log": {
        "description": "Generator operation log for College of Medicine backup power. Tracks diesel consumption and runtime.",
        "classification": "internal",
        "semantic_type": "fuel_consumption",
        "tags": ["fuel", "scope-1", "medical", "monthly", "aastmt", "alamein"],
    },
    "fleet_fuel_log": {
        "description": "Fleet fuel consumption log for AASTMT vehicles. Records gasoline and diesel per supplier per month.",
        "classification": "internal",
        "semantic_type": "fuel_consumption",
        "tags": ["fuel", "scope-1", "transport", "monthly", "aastmt", "alamein"],
    },
    "staff_travel": {
        "description": "Staff business travel records — destination, distance, and flight class for emission calculations.",
        "classification": "confidential",
        "semantic_type": "travel_record",
        "tags": ["transport", "scope-3", "monthly", "aastmt", "pii-sensitive"],
    },
    "hotels_electricity": {
        "description": "Monthly electricity consumption for AASTMT Hotels. Tracks kWh usage per building and meter.",
        "classification": "internal",
        "semantic_type": "energy_consumption",
        "tags": ["electricity", "scope-2", "monthly", "aastmt", "alamein"],
    },
    "hotels_chilled_water": {
        "description": "Chilled water consumption for AASTMT Hotels cooling systems. Measured in tons of refrigeration (TR).",
        "classification": "internal",
        "semantic_type": "cooling_consumption",
        "tags": ["energy", "scope-2", "monthly", "aastmt", "alamein"],
    },
    "hotels_water": {
        "description": "Monthly water consumption for AASTMT Hotels. Tracks cubic meters used per building and meter.",
        "classification": "internal",
        "semantic_type": "water_consumption",
        "tags": ["water", "scope-2", "monthly", "aastmt", "alamein"],
    },
    "hospital_electricity": {
        "description": "Monthly electricity consumption for the University Hospital. Tracks kWh per building and meter.",
        "classification": "internal",
        "semantic_type": "energy_consumption",
        "tags": ["electricity", "scope-2", "medical", "monthly", "aastmt", "alamein"],
    },
    "hospital_gen_log": {
        "description": "Generator operation log for University Hospital backup power. Records diesel and runtime per generator.",
        "classification": "internal",
        "semantic_type": "fuel_consumption",
        "tags": ["fuel", "scope-1", "medical", "monthly", "aastmt", "alamein"],
    },
    "medical_gas_log": {
        "description": "Medical gas consumption log — tracks gas types, quantities, and departments for anesthesia and clinical use.",
        "classification": "confidential",
        "semantic_type": "gas_consumption",
        "tags": ["medical", "scope-1", "monthly", "aastmt", "alamein"],
    },
    "hvac_refrigerant_log": {
        "description": "HVAC refrigerant service log — tracks R-410A usage for repairs, top-ups, and new installations.",
        "classification": "internal",
        "semantic_type": "refrigerant_usage",
        "tags": ["refrigerant", "scope-1", "medical", "monthly", "aastmt", "alamein"],
    },
    "hospital_water": {
        "description": "Monthly water consumption for University Hospital — tracks cubic meters per building and meter.",
        "classification": "internal",
        "semantic_type": "water_consumption",
        "tags": ["water", "scope-2", "medical", "monthly", "aastmt", "alamein"],
    },
    "finance_electricity": {
        "description": "Monthly electricity consumption for Logistics Affairs buildings — kWh and cost tracking.",
        "classification": "internal",
        "semantic_type": "energy_consumption",
        "tags": ["electricity", "scope-2", "monthly", "aastmt", "alamein"],
    },
    "office_supplies": {
        "description": "Office supplies procurement log — paper reams, types, and suppliers for emission factor calculations.",
        "classification": "internal",
        "semantic_type": "procurement",
        "tags": ["procurement", "scope-3", "monthly", "aastmt", "alamein"],
    },
    "med_procurement": {
        "description": "Medical procurement records — items, categories, and costs in USD for scope 3 emissions.",
        "classification": "confidential",
        "semantic_type": "procurement",
        "tags": ["procurement", "scope-3", "medical", "monthly", "aastmt", "alamein"],
    },
}

for title, adef in ASSET_DEFS.items():
    tbl = table_map.get(title)
    if not tbl:
        continue
    if tbl["id"] in existing_table_asset_ids:
        skipped += 1
        continue

    payload = {
        "data_table": tbl["id"],
        "description": adef["description"],
        "classification": adef["classification"],
        "semantic_type": adef["semantic_type"],
        "tags": adef["tags"],  # try by name
    }
    result = post("/catalog/assets/", payload)
    if result:
        created["assets"] += 1

# ── 6. DQ Rules ─────────────────────────────────────────────
print("\n🔍 DQ Rules...")
existing_rule_keys = set()
for r in existing_rules:
    existing_rule_keys.add((r.get("data_table"), r.get("data_field"), r.get("rule_type")))

DQ_RULES = {
    "med_electricity": [
        {"name": "Electricity period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Electricity building_id not null", "scope": "field", "field": "building_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Electricity consumption_kwh > 0", "scope": "field", "field": "consumption_kwh", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
        {"name": "Electricity cost_egp >= 0", "scope": "field", "field": "cost_egp", "rule_type": "range", "params": {"min": 0}, "severity": "warn"},
    ],
    "med_gen_log": [
        {"name": "Gen log period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Gen log generator_id not null", "scope": "field", "field": "generator_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Gen log diesel_liters > 0", "scope": "field", "field": "diesel_liters", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
        {"name": "Gen log runtime_hours >= 0", "scope": "field", "field": "runtime_hours", "rule_type": "range", "params": {"min": 0}, "severity": "warn"},
    ],
    "fleet_fuel_log": [
        {"name": "Fleet period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Fleet vehicle_count > 0", "scope": "field", "field": "vehicle_count", "rule_type": "range", "params": {"min": 1}, "severity": "error"},
        {"name": "Fleet gasoline_liters >= 0", "scope": "field", "field": "gasoline_liters", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
        {"name": "Fleet diesel_liters >= 0", "scope": "field", "field": "diesel_liters", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
        {"name": "Fleet total_cost_egp >= 0", "scope": "field", "field": "total_cost_egp", "rule_type": "range", "params": {"min": 0}, "severity": "warn"},
    ],
    "staff_travel": [
        {"name": "Travel period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Travel staff_name not null", "scope": "field", "field": "staff_name", "rule_type": "not_null", "severity": "error"},
        {"name": "Travel destination not null", "scope": "field", "field": "destination", "rule_type": "not_null", "severity": "error"},
        {"name": "Travel distance_km > 0", "scope": "field", "field": "distance_km", "rule_type": "range", "params": {"min": 0.1}, "severity": "error"},
    ],
    "hotels_electricity": [
        {"name": "Hotels Elec period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Hotels Elec building_id not null", "scope": "field", "field": "building_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Hotels Elec consumption_kwh > 0", "scope": "field", "field": "consumption_kwh", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "hotels_chilled_water": [
        {"name": "Chilled Water period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Chilled Water meter_id not null", "scope": "field", "field": "meter_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Chilled Water consumption_tr > 0", "scope": "field", "field": "consumption_tr", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "hotels_water": [
        {"name": "Hotels Water period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Hotels Water building_id not null", "scope": "field", "field": "building_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Hotels Water consumption_m3 > 0", "scope": "field", "field": "consumption_m3", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "hospital_electricity": [
        {"name": "Hosp Elec period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Elec building_id not null", "scope": "field", "field": "building_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Elec consumption_kwh > 0", "scope": "field", "field": "consumption_kwh", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
        {"name": "Hosp Elec cost_egp >= 0", "scope": "field", "field": "cost_egp", "rule_type": "range", "params": {"min": 0}, "severity": "warn"},
    ],
    "hospital_gen_log": [
        {"name": "Hosp Gen period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Gen generator_id not null", "scope": "field", "field": "generator_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Gen diesel_liters > 0", "scope": "field", "field": "diesel_liters", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "medical_gas_log": [
        {"name": "Med Gas period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Med Gas gas_type not null", "scope": "field", "field": "gas_type", "rule_type": "not_null", "severity": "error"},
        {"name": "Med Gas quantity_kg > 0", "scope": "field", "field": "quantity_kg", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "hvac_refrigerant_log": [
        {"name": "HVAC period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "HVAC unit_id not null", "scope": "field", "field": "unit_id", "rule_type": "not_null", "severity": "error"},
        {"name": "HVAC r410a_kg > 0", "scope": "field", "field": "r410a_kg", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "hospital_water": [
        {"name": "Hosp Water period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Water building_id not null", "scope": "field", "field": "building_id", "rule_type": "not_null", "severity": "error"},
        {"name": "Hosp Water consumption_m3 > 0", "scope": "field", "field": "consumption_m3", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "finance_electricity": [
        {"name": "Finance Elec period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Finance Elec consumption_kwh > 0", "scope": "field", "field": "consumption_kwh", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "office_supplies": [
        {"name": "Office Supplies period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Office Supplies paper_reams > 0", "scope": "field", "field": "paper_reams", "rule_type": "range", "params": {"min": 0}, "severity": "error"},
    ],
    "med_procurement": [
        {"name": "Procurement period_month not null", "scope": "field", "field": "period_month", "rule_type": "not_null", "severity": "error"},
        {"name": "Procurement item_name not null", "scope": "field", "field": "item_name", "rule_type": "not_null", "severity": "error"},
        {"name": "Procurement cost_usd > 0", "scope": "field", "field": "cost_usd", "rule_type": "range", "params": {"min": 0.01}, "severity": "error"},
    ],
}

for table_title, rules in DQ_RULES.items():
    tbl = table_map.get(table_title)
    if not tbl:
        continue
    tid = tbl["id"]
    tbl_fields = {f["name"]: f for f in field_map.get(tid, [])}

    for rule_def in rules:
        field_name = rule_def.get("field")
        fid = tbl_fields.get(field_name, {}).get("id") if field_name else None

        # skip if already exists
        key = (tid, fid, rule_def["rule_type"])
        if key in existing_rule_keys:
            skipped += 1
            continue

        payload = {
            "name": rule_def["name"],
            "scope": rule_def["scope"],
            "data_table": tid,
            "data_field": fid,
            "rule_type": rule_def["rule_type"],
            "params": rule_def.get("params", {}),
            "severity": rule_def["severity"],
            "is_active": True,
        }
        result = post("/dq/rules/", payload)
        if result:
            created["dq_rules"] += 1
            existing_rule_keys.add(key)

# ── 7. Governance Policies (one per module) ─────────────────
print("\n🛡️  Governance Policies...")
MODULE_POLICIES = {
    1: {"name": "Medicine Carbon — Table Delete Protection",
        "description": "Prevents accidental deletion of Medicine Carbon tables with data rows. Requires admin override.",
        "config": {"check_row_count": True, "max_rows": 0, "block_with_dependencies": True},
        "error_message": "Medicine Carbon tables with data cannot be deleted. Archive rows first or contact admin.",
        "remediation_steps": ["Archive all rows in the table before deletion", "Contact platform administrator for force-delete"]},
    2: {"name": "Logistics Carbon — Table Delete Protection",
        "description": "Prevents accidental deletion of Logistics/Finance Carbon tables with data rows.",
        "config": {"check_row_count": True, "max_rows": 0, "block_with_dependencies": True},
        "error_message": "Logistics Carbon tables with data cannot be deleted. Archive rows first or contact admin.",
        "remediation_steps": ["Archive all rows in the table before deletion", "Contact platform administrator for force-delete"]},
    3: {"name": "Transport Carbon — Table Delete Protection",
        "description": "Prevents accidental deletion of Transport Carbon tables (fleet fuel & staff travel).",
        "config": {"check_row_count": True, "max_rows": 0, "block_with_dependencies": True},
        "error_message": "Transport Carbon tables with data cannot be deleted. Archive rows first or contact admin.",
        "remediation_steps": ["Archive all rows in the table before deletion", "Contact platform administrator for force-delete"]},
    4: {"name": "Hotels Carbon — Table Delete Protection",
        "description": "Prevents accidental deletion of Hotels Carbon tables with consumption data.",
        "config": {"check_row_count": True, "max_rows": 0, "block_with_dependencies": True},
        "error_message": "Hotels Carbon tables with data cannot be deleted. Archive rows first or contact admin.",
        "remediation_steps": ["Archive all rows in the table before deletion", "Contact platform administrator for force-delete"]},
    5: {"name": "Hospital Carbon — Table Delete Protection",
        "description": "Prevents accidental deletion of Hospital Carbon tables with clinical and utility data.",
        "config": {"check_row_count": True, "max_rows": 0, "block_with_dependencies": True},
        "error_message": "Hospital Carbon tables with data cannot be deleted. Archive rows first or contact admin.",
        "remediation_steps": ["Archive all rows in the table before deletion", "Contact platform administrator for force-delete"]},
}

existing_policy_names = {p.get("name") for p in existing_policies}
for mid, pdef in MODULE_POLICIES.items():
    if pdef["name"] in existing_policy_names:
        skipped += 1
        continue
    payload = {
        "policy_type": "table_delete",
        "name": pdef["name"],
        "description": pdef["description"],
        "enabled": True,
        "scope_type": "global",
        "config": pdef["config"],
        "error_message": pdef["error_message"],
        "remediation_steps": pdef["remediation_steps"],
    }
    result = post("/catalog/governance-policies/", payload)
    if result:
        created["policies"] += 1

# ── 8. Reference Sets ───────────────────────────────────────
print("\n📚 Reference Sets...")
REF_SETS = {
    "Building Codes — Alamein Campus": {
        "description": "Standard building identifiers for the New Alamein campus",
        "values": [
            {"code": "BLDG_MED_01", "label": "Medicine Building A", "is_active": True},
            {"code": "BLDG_MED_02", "label": "Medicine Building B (Labs)", "is_active": True},
            {"code": "BLDG_HOSP_01", "label": "University Hospital Main", "is_active": True},
            {"code": "BLDG_HOSP_02", "label": "University Hospital Annex", "is_active": True},
            {"code": "BLDG_HTL_01", "label": "Hotel Tower A", "is_active": True},
            {"code": "BLDG_HTL_02", "label": "Hotel Tower B", "is_active": True},
            {"code": "BLDG_LOG_01", "label": "Logistics Headquarters", "is_active": True},
            {"code": "BLDG_ADM_01", "label": "Administration Building", "is_active": True},
        ],
    },
    "Generator IDs — Alamein Campus": {
        "description": "Backup diesel generator identifiers across campus",
        "values": [
            {"code": "GEN_MED_01", "label": "Medicine Generator 250kVA", "is_active": True},
            {"code": "GEN_MED_02", "label": "Medicine Generator 150kVA", "is_active": True},
            {"code": "GEN_HOSP_01", "label": "Hospital Generator 500kVA", "is_active": True},
            {"code": "GEN_HOSP_02", "label": "Hospital Generator 300kVA", "is_active": True},
            {"code": "GEN_HTL_01", "label": "Hotels Generator 400kVA", "is_active": True},
        ],
    },
    "Gas Types — Medical": {
        "description": "Medical gas types used in healthcare settings",
        "values": [
            {"code": "O2", "label": "Oxygen (O₂)", "is_active": True},
            {"code": "N2O", "label": "Nitrous Oxide (N₂O)", "is_active": True},
            {"code": "MED_AIR", "label": "Medical Air", "is_active": True},
            {"code": "CO2", "label": "Carbon Dioxide (CO₂)", "is_active": True},
            {"code": "N2", "label": "Nitrogen (N₂)", "is_active": True},
            {"code": "HELIUM", "label": "Helium (He)", "is_active": True},
        ],
    },
    "Service Types — HVAC": {
        "description": "HVAC service types for refrigerant log",
        "values": [
            {"code": "TOP_UP", "label": "Refrigerant Top-Up", "is_active": True},
            {"code": "REPAIR", "label": "Leak Repair & Recharge", "is_active": True},
            {"code": "INSTALL", "label": "New Unit Installation", "is_active": True},
            {"code": "MAINT", "label": "Preventive Maintenance", "is_active": True},
            {"code": "RETIRE", "label": "Unit Decommissioning", "is_active": True},
        ],
    },
    "Departments — Medicine & Hospital": {
        "description": "Clinical and administrative departments",
        "values": [
            {"code": "SURGERY", "label": "General Surgery", "is_active": True},
            {"code": "ICU", "label": "Intensive Care Unit", "is_active": True},
            {"code": "ER", "label": "Emergency Room", "is_active": True},
            {"code": "RADIOLOGY", "label": "Radiology & Imaging", "is_active": True},
            {"code": "ANESTHESIA", "label": "Anesthesiology", "is_active": True},
            {"code": "PHARMACY", "label": "Pharmacy", "is_active": True},
            {"code": "LAB", "label": "Clinical Laboratory", "is_active": True},
            {"code": "ADMIN", "label": "Hospital Administration", "is_active": True},
        ],
    },
    "Flight Class": {
        "description": "Flight class codes for staff travel emission factors",
        "values": [
            {"code": "ECONOMY", "label": "Economy Class", "is_active": True},
            {"code": "PREMIUM_ECO", "label": "Premium Economy", "is_active": True},
            {"code": "BUSINESS", "label": "Business Class", "is_active": True},
            {"code": "FIRST", "label": "First Class", "is_active": True},
        ],
    },
    "Supplier Categories": {
        "description": "Supplier and procurement categories",
        "values": [
            {"code": "LOCAL", "label": "Local Supplier", "is_active": True},
            {"code": "NATIONAL", "label": "National Distributor", "is_active": True},
            {"code": "INTL", "label": "International Vendor", "is_active": True},
            {"code": "GOVT", "label": "Government Supplier", "is_active": True},
        ],
    },
}

existing_refset_names = {r["name"] for r in existing_refsets}
for rs_name, rs_def in REF_SETS.items():
    if rs_name in existing_refset_names:
        skipped += 1
        continue

    # Create reference set
    rs_payload = {"name": rs_name, "description": rs_def["description"], "lifecycle_state": "active"}
    rs_result = post("/mdm/reference-sets/", rs_payload)
    if not rs_result:
        continue
    created["ref_sets"] += 1
    rs_id = rs_result["id"]

    # Create values using bulk-create endpoint (reference_set is read-only on serializer)
    values_list = [{"code": v["code"], "label": v["label"], "is_active": v["is_active"]} for v in rs_def["values"]]
    vr = requests.post(
        f"{BASE}/mdm/reference-values/bulk-create/?reference_set={rs_id}",
        headers=H, json=values_list
    )
    if vr.status_code in (200, 201):
        created["ref_values"] += len(values_list)

# ── 9. Update table & module metadata ───────────────────────
print("\n📝 Updating metadata...")

# Update table descriptions
TABLE_DESCRIPTIONS = {
    "med_electricity": "Monthly electricity consumption records for College of Medicine — kWh, cost per building",
    "med_gen_log": "Generator operation logs for College of Medicine — diesel consumption, runtime hours",
    "fleet_fuel_log": "Fleet fuel logs — gasoline & diesel per vehicle, per supplier, per month",
    "staff_travel": "Staff business travel records — destination, distance, and flight class",
    "hotels_electricity": "Monthly electricity consumption for AASTMT Hotels buildings",
    "hotels_chilled_water": "Chilled water consumption for hotel cooling systems (tons of refrigeration)",
    "hotels_water": "Monthly water consumption for AASTMT Hotels (cubic meters)",
    "hospital_electricity": "Monthly electricity for University Hospital — kWh and cost per building",
    "hospital_gen_log": "Generator logs for University Hospital backup power",
    "medical_gas_log": "Medical gas consumption — types, quantities, departments",
    "hvac_refrigerant_log": "HVAC refrigerant service log — R-410A usage tracking",
    "hospital_water": "Monthly water consumption for University Hospital (cubic meters)",
    "finance_electricity": "Monthly electricity for Logistics Affairs buildings",
    "office_supplies": "Office supplies procurement — paper reams, types, suppliers",
    "med_procurement": "Medical procurement records — items, categories, costs in USD",
}

for title, desc in TABLE_DESCRIPTIONS.items():
    tbl = table_map.get(title)
    if not tbl:
        continue
    if tbl.get("description") != desc:
        ok = patch(f"/dataschema/tables/{tbl['id']}/", {"description": desc})
        if ok:
            created["updated"] += 1

# Update module descriptions
MODULE_DESCRIPTIONS = {
    1: "Carbon footprint data for the College of Medicine — electricity, backup generators, medical gases, HVAC refrigerants, and water consumption across medical buildings",
    2: "Carbon footprint data for Logistics Affairs (الشؤون المادية) — electricity, office supplies procurement, and medical procurement for scope 1, 2, and 3 emissions",
    3: "Carbon footprint data for AASTMT Transportation (النقل) — fleet fuel consumption and staff business travel records",
    4: "Carbon footprint data for AASTMT Hotels — electricity, chilled water, and water consumption across hotel towers",
    5: "Carbon footprint data for the University Hospital — electricity, backup generators, medical gases, HVAC refrigerants, and water consumption",
}

for mid, desc in MODULE_DESCRIPTIONS.items():
    mod = module_map.get(mid)
    if not mod:
        continue
    if mod.get("description") != desc:
        ok = patch(f"/core/modules/{mid}/", {"description": desc})
        if ok:
            created["updated"] += 1

# ── REPORT ──────────────────────────────────────────────────
print("\n" + "=" * 55)
print("🎉 CARBON DATA TRUST CORE — SEED COMPLETE")
print("=" * 55)
print(f"  🏛️  Data Domains:        +{created['domains']}")
print(f"  🏷️  Tags:                +{created['tags']}")
print(f"  📖 Glossary Terms:       +{created['glossary']}")
print(f"  📋 Asset Profiles:       +{created['assets']}")
print(f"  🔍 DQ Rules:             +{created['dq_rules']}")
print(f"  🛡️  Governance Policies:  +{created['policies']}")
print(f"  📚 Reference Sets:       +{created['ref_sets']}")
print(f"  📎 Reference Values:     +{created['ref_values']}")
print(f"  📝 Metadata Updated:     {created['updated']}")
print(f"  ⏭️  Skipped (existing):   {skipped}")
print(f"\n  TOTAL NEW ITEMS:        {sum(created.values())}")
print("=" * 55)
print("\n✅ Ready for data entry. No rows, no emission factors, no calc rules created.")
