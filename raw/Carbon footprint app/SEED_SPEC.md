# AASTMT Carbon Seed Spec — from raw files → Carbon Data Trust Platform

> **Scope rule (agreed):** seed **only data that actually exists** in the two source
> files. Do **not** fabricate or backfill missing numbers. Where a category exists but
> has no measured value yet, seed it as `pending` (taxonomy present, no number).
> Where the source is absent at that campus, seed it as `not_applicable`.

---

## 1. Source files

| File | Type | Content | Fiscal period |
|---|---|---|---|
| `Smart_ ...Magdy (1).xlsx` | Excel (structured) | Smart Village GHG inventory + monthly meters | FY 2023-24 |
| `البصمة الكربونية.pdf` | scanned PDF (8 pp, Arabic) | Abu Qir electricity, Aswan/South Valley scopes + refrigerants + fuel | FY 2025-26 |

The PDF has **no text layer** (image scans). Arabic content was translated manually and
is hardcoded into `export_csv.py`. The Excel is machine-readable and is the authoritative
source for Smart Village.

## 2. What campus has what data (no fabrication)

| Campus | Has data? | What | Fiscal year | Source |
|---|---|---|---|---|
| **Giza Smart Village** | ✅ full | GHG inventory (S1/S2/S3) + monthly electricity/water/chilled-water | 2023-24 | Excel |
| **Abu Qir** | ✅ partial | monthly electricity only (8,059,531 kWh) | 2025-26 | PDF p2 |
| **Aswan South Valley** | ✅ partial | Scope 1 + 2 + 3 activity + refrigerants + fuel report | 2025-26 | PDF p3-6,8 |
| Dokki / Heliopolis / Alamein / Miami / Latakia / Port Said | ❌ none | — | — | listed on PDF p1 only |

> **Proof Excel = Smart Village only:** Excel `2023-2024` electricity (2,704,187 kWh)
> equals Excel `Detailed data` total exactly, which meters only buildings 401 + 2401.
> Abu Qir alone is ~3× that (8.06M kWh). So the Excel is not a combined figure.

## 3. Generated CSVs (`raw/csv/`)

Regenerate anytime with `.venv/bin/python raw/export_csv.py`.

| CSV | Rows | Schema |
|---|---|---|
| `campuses.csv` | 9 | `name, slug, city, full_name, has_data` |
| `smart_village_inventory_fy2324.csv` | 55 | `scope, category, source_of_emission, activity_data, description_ar, existence, unit, quantity` |
| `smart_village_monthly_electricity.csv` | 26 | `month, building_401_kwh, building_2401_kwh, total_kwh` |
| `smart_village_monthly_water.csv` | 18 | `month, building_401_m3, building_2401_m3, total_m3` |
| `smart_village_monthly_chilled_water.csv` | 20 | `month, meter_2401_1_tr, meter_2401_2_tr, total_tr` |
| `abu_qir_monthly_electricity_fy2526.csv` | 12 | `month, total_kwh` |
| `refrigerants_fy2526.csv` | 4 | `campus, refrigerant, cylinders_count, notes` |
| `south_valley_scope12_fy2526.csv` | 6 | `scope, category, source, activity_data, unit, quantity` |
| `south_valley_scope3_fy2526.csv` | 15 | `category, activity_data, unit, quantity` |
| `abu_qir_fuel_fy2526.csv` | 12 | `month, gasoline_92_l, gasoline_95_l, diesel_l` |

### Existence classification (inventory CSV)

| `existence` | meaning | `quantity` |
|---|---|---|
| `present` | source exists at campus, measured | number |
| `not_applicable` | source absent (`-` / "Not Applicable") | empty |
| `pending` | source exists but not yet measured (`Pending ?`) | empty |

---

## 4. Mapping → Carbon platform entities

Canonical hierarchy: **OrgUnit → Module (Data Product) → DataTable → DataField → DataRow**
with an `emissions` calculation layer on top.

### 4.1 OrgUnits (`mdm.OrgUnit`, self-ref tree)

```
AASTMT                                  (university)  [root]
├─ Giza Smart Village                   (campus)      ← FY23-24 data
│   ├─ Facilities & Utilities           (department)
│   ├─ Energy / Utilities               (department)
│   ├─ Transportation / Fleet           (department)
│   ├─ Procurement                      (department)
│   └─ Campus Services                  (department)
├─ Abu Qir                              (campus)      ← FY25-26 electricity
├─ Aswan South Valley                   (campus)      ← FY25-26 S1/S2/S3
├─ Giza Dokki                           (campus, no data)
├─ Cairo Heliopolis                     (campus, no data)
├─ New Alamein                          (campus, no data)
├─ Alexandria Miami                     (campus, no data)
├─ Syria Latakia                        (campus, no data)
└─ Port Said                            (campus, no data)
```

Buildings **401 / 2401** → `ReferenceSet "buildings"` (not OrgUnits) for now; promote to
`org_type='facility'` only if building-level RBAC is needed later.

### 4.2 MDM Reference Sets

| `ReferenceSet` | values |
|---|---|
| `campuses` | 9 branches (from `campuses.csv`) |
| `buildings` | 401, 2401 |
| `fuel_types` | natural_gas, diesel, gasoline, lpg, r22, r134a, r404a, r410a |
| `refrigerants` | R-134a, R-410A, R-407C, R-404A, R-22, other |
| `fire_suppressants` | dry_powder (طفاية بودرة), co2 (طفاية CO2), dry_chemical (مسحوق كيماوي جاف), fm200 |
| `ghg_categories` | stationary_combustion, mobile_combustion, fugitive, purchased_energy, consumables, capital_goods, fertilizers, fuel_energy, water_waste, commuting, waste, business_travel, leased_assets |
| `units` | kwh, m3, tr, l, kg, m2, km, ton, unit, tissue, paper |
| `existence` | present, not_applicable, pending |

### 4.3 Data Products (Modules) & scopes

A Module is a **governed container of multiple tables** (the UI's "Data Product"), so we
create **3 data products** — one per campus — each holding that campus's tables. The
advisory `scope` is a coarse whole-product tag only; authoritative scope comes from the
emission factor at calculation time (see §5).

| Module (Data Product) | advisory scope | org | tables |
|---|---|---|---|
| Smart Village — Carbon Footprint | 2 | Giza Smart Village | `monthly_electricity`, `monthly_chilled_water`, `monthly_water`, `ghg_inventory` |
| Abu Qir — Carbon Footprint | 2 | Abu Qir | `monthly_electricity`, `monthly_fuel`, `refrigerants` |
| South Valley — Carbon Footprint | 1 | Aswan South Valley | `scope12_activity`, `scope3_activity` |

### 4.4 Tables → Fields

**Monthly series (shared shape, per campus):**

`monthly_electricity` — `month`(date,req), `building_401_kwh`(number≥0), `building_2401_kwh`(number≥0), `total_kwh`(number≥0)
`monthly_water` — `month`(date,req), `building_401_m3`, `building_2401_m3`, `total_m3`
`monthly_chilled_water` — `month`(date,req), `meter_2401_1_tr`, `meter_2401_2_tr`, `total_tr`
`monthly_fuel` (Abu Qir) — `month`(date,req), `gasoline_92_l`, `gasoline_95_l`, `diesel_l`

**Inventory / activity tables:**

`ghg_inventory` — `scope`, `category`(ref→ghg_categories), `source_of_emission`, `activity_data`(ref→fuel_types|refrigerants|fire_suppressants), `existence`(ref→existence), `unit`(ref→units), `quantity`(number, nullable)
`scope12_activity` — `scope`, `category`, `source`, `activity_data`, `unit`, `quantity`
`scope3_activity` — `category`, `activity_data`, `unit`, `quantity`
`refrigerants` — `campus`(ref→campuses), `refrigerant`(ref), `cylinders_count`(number), `notes`

### 4.5 Data Rows volume

| table | rows | notes |
|---|---|---|
| `monthly_electricity` (SV) | 26 | Oct/Nov 2024 + May/Jun 2025 absent → not seeded |
| `monthly_water` (SV) | 18 | Jan 2023–Jun 2024 |
| `monthly_chilled_water` (SV) | 20 | Jan 2023–Jul 2024 + Feb 2025 |
| `ghg_inventory` (SV) | 54 | incl. `pending` + `not_applicable` rows |
| `monthly_electricity` (Abu Qir) | 12 | Jun 2026 blank → not seeded |
| `monthly_fuel` (Abu Qir) | 12 | gasoline_92 114,190.7 / gasoline_95 2,936 / diesel 643,548.69 L |
| `scope12_activity` (SV/Aswan) | 6 | |
| `scope3_activity` (SV/Aswan) | 15 | |
| `refrigerants` | 4 | |
| **Total** | **167** | across 9 tables / 3 data products |

## 5. Emissions calculation layer

### 5.1 Emission Factors (global, not org-scoped)

| code | scope | factor | activity unit |
|---|---|---|---|
| `EG_GRID_2024` | 2 | 0.4584 kg CO2e | kWh *(exists)* |
| `EG_WATER_2024` | 3 | 0.3440 kg CO2e | m³ *(exists)* |
| `CHILLED_WATER_COP3.5` | 2 | 0.4606 kg CO2e | TR·h *(new — see §5.2)* |

Additional factors to add — **DEFRA 2024 convention (chosen; editable placeholders)**,
consistent with `EG_WATER_2024` (already "DEFRA-based proxy"):

| code | scope | factor (kg CO2e) | activity unit | source |
|---|---|---|---|---|
| `DEFRA_DIESEL` | 1 | 2.51 | L | DEFRA 2024, diesel (100% mineral) |
| `DEFRA_GASOLINE` | 1 | 2.19 | L | DEFRA 2024, petrol (100% mineral) |
| `DEFRA_NATURAL_GAS` | 1 | 2.02 | m³ | DEFRA 2024, natural gas (gross CV) |
| `DEFRA_LPG` | 1 | 1.52 | kg | DEFRA 2024, LPG (gross CV) |

Remaining (paper, waste, water-waste, commuting, fertilizer, T&D losses, capital
goods) → add as **editable placeholders** with `factor_value` = 0 and `notes` =
"factor TBD — needs source", so the taxonomy + rules exist but no CO2e is
fabricated.

### 5.2 Chilled Water methodology — **CONFIRMED COP 3.5**

$$\text{kg CO}_2\text{e per TR·h} = \frac{3.51685}{\text{COP}} \times 0.4584$$

- COP 3.5 → **0.4606 kg CO2e / TR·h**
- FY23-24 total 1,962,093.2 TR → **≈ 904 t CO2e**

`setup_carbon_app.py` currently leaves chilled water *unwired* (methodology TBD). Seed must:
1. add `CHILLED_WATER_COP3.5` factor,
2. add a `CalculationRule` (`rule_type='direct'`, `date_field=month`, `activity_field=total_tr`),
3. run `calculate_for_table()`.

### 5.3 GWP (for refrigerants)

| gas | GWP (AR5/AR6) |
|---|---|
| CO2 | 1 |
| R-22 | 1810 |
| R-134a | 1430 |
| R-404A | 3922 |
| R-410A | 2088 |
| R-407C | 1774 |
| SF₆ | 23500 |
| N₂O | 265 |

### 5.4 ReportingPeriods

| name | start | end | type | org |
|---|---|---|---|---|
| `FY 2023-24` | 2023-07-01 | 2024-06-30 | annual (baseline) | Smart Village |
| `FY 2025-26` | 2025-07-01 | 2026-06-30 | annual | Abu Qir, Aswan South Valley |

### 5.5 CalculationRule bindings

| table | activity_field | date_field | factor | output |
|---|---|---|---|---|
| SV `monthly_electricity` | `total_kwh` | `month` | EG_GRID_2024 | scope 2 |
| SV `monthly_water` | `total_m3` | `month` | EG_WATER_2024 | scope 3 |
| SV `monthly_chilled_water` | `total_tr` | `month` | CHILLED_WATER_COP3.5 | scope 2 |
| Abu Qir `monthly_electricity` | `total_kwh` | `month` | EG_GRID_2024 | scope 2 |
| Abu Qir `monthly_fuel` | `diesel_l` | `month` | DEFRA_DIESEL | scope 1 |
| Abu Qir `monthly_fuel` | `gasoline_92_l` | `month` | DEFRA_GASOLINE | scope 1 |
| Abu Qir `monthly_fuel` | `gasoline_95_l` | `month` | DEFRA_GASOLINE | scope 1 |
| SV `ghg_inventory` | `quantity` | — | per-fuel/per-refrigerant factors | scope 1/3 |

---

## 6. Seed script plan

Write `backend/core/management/commands/seed_carbon_raw.py` (idempotent, additive, mirrors
`seed_aastmt_data.py` + `setup_carbon_app.py`):

1. Load CSVs from `raw/csv/` (or embed as Python literals, matching existing pattern).
2. Create 9 campus `OrgUnit`s under AASTMT root; departments under Smart Village.
3. Create `ReferenceSet`s + `ReferenceValue`s (§4.2).
4. Create `Module`s + `DataTable`s + `DataField`s (§4.4).
5. Insert `DataRow`s (§4.5) — **skip blank months / blank quantities**.
6. Seed `EmissionFactor`s + `GWP`s + `ReportingPeriod`s (§5).
7. Bind `CalculationRule`s + compute (§5.5).
8. Print a summary (rows created per table, total tCO2e).

## 7. Open items needing user confirmation

1. ✅ **`refrigerants_fy2526.csv` (PDF p3)** — RESOLVED: **main campus = Abu Qir**.
   Refrigerant cylinders attributed to Abu Qir, FY 2025-26.
2. ✅ **`abu_qir_fuel_fy2526.csv` (PDF p8)** — liters filled from user-provided
   table; attributed to **Abu Qir (main campus)** per user.
3. **Abu Qir June 2026** — blank in source; confirm it's genuinely missing (leave out).
4. ✅ **Diesel/gasoline/natural-gas emission factors** — RESOLVED: **DEFRA 2024**
   convention (§5.1), consistent with existing `EG_WATER_2024`.
5. ✅ **Fuel report (PDF p8) campus** — RESOLVED: **Abu Qir** (main campus).
   Diesel total 643,548 L ~5x South Valley's Scope-1 diesel → belongs to Abu Qir.
