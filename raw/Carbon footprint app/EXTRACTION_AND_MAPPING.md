# AASTMT Raw Data → Carbon Platform — Extraction & Mapping

Source files (in this folder):
1. `Smart_ AASTMT Carbon Emmission_07-07-2025_Magdy (1).xlsx` — **structured** (2 sheets)
2. `البصمة الكربونية.pdf` — **scanned report**, 8 pages (image-only, no text layer)

---

## PART A — WHAT THE RAW DATA CONTAINS

### A.1 Excel — Sheet "2023-2024" (GHG inventory template, Smart Village campus)

Title cell: `Main Components of AASTMT Carbon Footprint`
Subtitle cell: `This data includes the three campuses: Smart Village` (the author names only Smart Village; the data is Smart-Village-specific).

Columns: `Category | Source of Emission (مصدر الإنبعاثات) | Description (الوصف التفصيلي) | Activity Data (نوع النشاط) | Existence (التواجد) | Data Unit (الوحدة) | Quantity (الكمية)`

It is a full GHG-Protocol inventory structured by **Scope 1 / 2 / 3**, with fuel/source rows, units, and quantities. Complete dump:

#### SCOPE 1 — Direct
| Category | Source | Fuel / Activity | Unit | Quantity |
|---|---|---|---|---|
| Stationary Combustion | Boilers / Water heaters | Natural Gas | m³ | `-` |
| | | Other fuel | | `-` |
| | On-site Power Generators | Natural Gas | m³ | `-` |
| | | **Diesel** | L | **3,000** |
| | | Gasoline | L | `-` |
| | Laboratory (burners) | Natural Gas | m³ | `-` |
| | | Diesel | L | `-` |
| | | Gasoline | L | `-` |
| | | LPG | Kg | `-` |
| | Campus Kitchens / Canteens | Natural Gas | m³ | `-` |
| | | LPG | Kg | `-` |
| Mobile Combustion | Company vehicles | Gasoline | L | `-` |
| | | **Diesel** | L | **5,161** |
| | | Natural gas | m³ | `-` |
| Fugitive Emissions | Refrigeration & AC | R-134a | Kg | `-` |
| | | R-410A | Kg | `-` |
| | | R-407C | Kg | `-` |
| | | Other | Kg | `-` |
| | Fire Suppression | طفاية بودرة (dry powder) | Kg | **246** |
| | | طفاية CO2 | Kg | **590** |
| | | مسحوق كيماوي جاف (dry chemical) | Kg | **12** |
| | | FM200 | Kg | `Pending ?` |
| | Laboratory Gas Systems | SF₆ | Kg | `-` |
| | | N₂O | Kg | `-` |
| | | Other | Kg | `-` |

#### SCOPE 2 — Purchased Energy
| Source | Activity | Unit | Quantity |
|---|---|---|---|
| Purchased electricity | KWh | KWh | **2,704,187** |
| Purchased steam | Ton/GJ | Ton/GJ | `-` |
| Purchased heating | KWh/GJ | KWh/GJ | `-` |
| Purchased cooling | Ton of Refrigeration | TR | **1,962,093.20** |

#### SCOPE 3 — Value Chain
| Category | Source | Activity | Unit | Quantity |
|---|---|---|---|---|
| Purchased goods & services | Papers | Paper | paper | **2,500,000** |
| | | Envelope | Unit | **50,000** |
| | Inks | Cartridges / Toner | Unit | **400** |
| | Hygiene | Soap | L | **3,600** |
| | | Tissues | tissue | **1,660,000** |
| | Plastic | Folders | Unit | **2,000** |
| | Food | Meal | Unit | `Pending ?` |
| Capital Goods | Furniture | — | — | `Pending ?` |
| | Appliances | — | — | `Pending ?` |
| | Facilities | — | — | `-` |
| Fertilizers | Green Area (grass) | — | m² | **6,000** |
| Fuel & Energy Related | T&D losses | — | — | `-` |
| | Fuel transport | — | — | `-` |
| Water Usage/Waste | Annual Water Consumption | — | m³ | **11,490** |
| | Water Waste | — | m³ | **10,341** |
| Annual Commuting | Student | — | km | `Pending ?` |
| | Employee | — | km | `Pending ?` |
| Waste | Waste Disposal | — | ton | **73** |
| | Waste Treatment | — | — | `-` |
| Business travel | Air Ticket | — | — | *(empty)* |
| Upstream transport | Purchased Goods | — | — | `-` |
| Upstream Leased Assets | Rented vehicles | Diesel | L | **12,900** |
| | Rented office buildings | Electricity | — | `-` |
| | | Water | — | `-` |
| | | Diesel | — | `-` |

### A.2 Excel — Sheet "Detailed data" (monthly meter time-series)

Three meter series, all Smart Village, buildings **401** and **2401**:

**Electricity (KWh)** — meters `401` + `2401`
- Span: Jan 2023 → Jun 2025 (**30 months**)
- Total = **2,704,187 kWh**
- Jan 2023 = 115,382 + 120,610 = 235,992 kWh … (monthly totals provided)

**Water (m³)** — meters `401` + `2401`
- Span: Jan 2023 → Jun 2024 (**18 months**)
- Total = **11,490 m³**

**Chilled Water (TR)** — meters `2401-1` + `2401-2`
- Span: Jan 2023 → Feb 2025 (**26 months**)
- Total = **1,962,093.20 TR**

### A.3 PDF — "البصمة الكربونية" (Carbon Footprint report), 8 pages, scanned

OCR (RapidOCR, English/numerics only — Arabic text is **not** machine-readable with available tooling):

- **Page 1** — campus list (9 branches) + `www.aast.edu` + `12/909207`:
  1. Abu Qir
  2. Giza – Dokki Branch
  3. Giza – Smart Village Branch
  4. Cairo – Heliopolis Branch
  5. New Alamein City – Alamein Branch
  6. Alexandria – Miami Branch
  7. Syria – Latakia Branch
  8. Port Said – Port Said Branch
  9. Aswan – South Valley Branch
- **Page 2** — a numeric column (likely per-campus kWh or CO₂e):
  `1,027,668 | 879,868 | 987,273 | 788,411 | 787,030 | 639,797 | 483,663 | 519,901 | 483,481 | 506,693 | 871,945` (+ `(2025)`)
- **Pages 3–6** — Arabic-only narrative/tables → **NOT extractable (need manual help)**
- **Page 7** — consumables (partial OCR): envelopes ~155,000, paper 13,555/14,910, cartridges & ink 1,550/1,705, diesel 9,000/… kg, images & ink 2,000/2,200 unit
- **Page 8** — large numeric summary table (per-campus × metric), many figures

> **⛔ MANUAL HELP NEEDED** — pages 3–6 are Arabic-only and my OCR cannot read Arabic. Please describe: (a) the campus→number mapping on page 2, (b) the tables on pages 3–6, (c) page 8's column headers.

---

## PART B — THE CARBON PLATFORM TARGET MODEL (verified against live code)

Hierarchy: **OrgUnit → Module ("Data Product") → DataTable → DataField → DataRow**

| Layer | App | Models (live) |
|---|---|---|
| Org structure | `mdm` | `OrgUnit` (self-ref tree; `org_type`: university/campus/college/department/division/team/facility/other) |
| Reference data | `mdm` | `ReferenceSet`, `ReferenceValue` |
| Metadata engine | `dataschema` | `DataTable`, `DataField` (type/required/options/validation/reference_set), `DataRow` (JSON `values`) |
| Catalog/governance | `catalog` | `DataDomain`, `GlossaryTerm`, `Tag`, `AssetProfile`, `GovernancePolicy`, `GovernanceEvent`, `LineageEdge` |
| DQ | `dq` | `TableProfile`, `FieldProfile`, `DQRule`, `DQResult` |
| Carbon app | `emissions` | `EmissionFactor`, `GWP`, `ReportingPeriod`, `CalculationRule`, `Calculation`, `SBTiTarget`, `VerificationRecord`, `OrganizationalBoundary`, `BaseYear` |

**Scope semantics (must not conflate):**
1. **GHG Scope 1/2/3** = emissions taxonomy → authoritative on `EmissionFactor.scope` + `Calculation.scope`; advisory on `Module.scope`.
2. **Access scope** = OrgUnit subtree (RBAC).
3. **Module** = dataset container (may feed multiple scopes).

---

## PART C — SUGGESTED MAPPING

### C.1 OrgUnits (MDM tree)

```
AASTMT  (university, root)
├─ Abu Qir Campus            (campus)
├─ Giza Dokki Campus         (campus)
├─ Giza Smart Village Campus (campus)   ← data lives here
│   ├─ Facilities & Utilities   (department)
│   ├─ Energy / Utilities       (department)
│   ├─ Transportation / Fleet   (department)
│   ├─ Procurement              (department)
│   └─ Campus Services          (department)
├─ Cairo Heliopolis Campus   (campus)
├─ New Alamein Campus        (campus)
├─ Alexandria Miami Campus   (campus)
├─ Syria Latakia Campus       (campus)
├─ Port Said Campus          (campus)
└─ Aswan South Valley Campus (campus)
```

Buildings **401 / 2401**: model as `ReferenceSet` "Buildings" (recommended — keeps them as field-level reference values on meter fields) **or** as `OrgUnit(org_type='facility')` under Smart Village if you want building-level access control later.

### C.2 MDM Reference Sets

| ReferenceSet | Values |
|---|---|
| `campuses` | the 9 branches above |
| `buildings` | 401, 2401 |
| `fuel_types` | natural_gas, diesel, gasoline, lpg |
| `refrigerants` | R-134a, R-410A, R-407C, other |
| `fire_suppressants` | dry_powder, co2, dry_chemical, fm200 |
| `ghg_categories` | stationary_combustion, mobile_combustion, fugitive, purchased_energy, purchased_goods, capital_goods, fertilizers, water_waste, commuting, waste, business_travel, leased_assets |
| `units_of_measure` | kwh, m3, tr, l, kg, m2, km, ton, unit, tissue, paper |
| `existence` | applicable, not_applicable, pending |

### C.3 Metadata (catalog)

- **DataDomains**: Energy, Water, Cooling, Refrigerants, Waste, Transportation, Purchased Goods, Facilities, Commuting.
- **GlossaryTerms**: Scope 1/2/3, Activity Data, Emission Factor, CO₂e, GWP, Stationary Combustion, Fugitive Emissions, Chilled Water (TR), Lineage, tCO₂e.
- **Tags**: `smart-village`, `scope-1`, `scope-2`, `scope-3`, `metered`, `estimated`, `pending`.
- **AssetProfiles**: auto-provisioned per table → set owner/steward/classification (`internal`) per table.

### C.4 Data Products (Modules) + Scopes

| Module (Data Product) | Advisory scope | Tables |
|---|---|---|
| Smart Village — Electricity | 2 | `monthly_electricity` |
| Smart Village — Chilled Water | 2 | `monthly_chilled_water` |
| Smart Village — Water | 3 | `monthly_water` |
| Scope 1 — Combustion | 1 | `stationary_combustion`, `mobile_combustion` |
| Scope 1 — Fugitive | 1 | `fugitive_emissions` |
| Scope 3 — Consumables | 3 | `consumables` |
| Scope 3 — Water & Waste | 3 | `water_waste`, `waste` |
| Scope 3 — Leased Assets | 3 | `leased_assets` |
| Scope 3 — Other (commuting/fertilizer/capital/business-travel) | 3 | `commuting`, `fertilizers`, `capital_goods`, `business_travel` |

### C.5 Tables → Fields (DataTable / DataField)

**Time-series (3 core tables):**

`monthly_electricity` (30 rows)
- `month` (date, required)
- `building_401_kwh` (number, min 0)
- `building_2401_kwh` (number, min 0)
- `total_kwh` (number, min 0)

`monthly_water` (18 rows)
- `month` (date, required)
- `meter_401_m3` (number, min 0)
- `meter_2401_m3` (number, min 0)
- `total_m3` (number, min 0)

`monthly_chilled_water` (26 rows)
- `month` (date, required)
- `meter_2401_1_tr` (number, min 0)
- `meter_2401_2_tr` (number, min 0)
- `total_tr` (number, min 0)

**Inventory tables (scope 1 & 3):**

`stationary_combustion` — `source`(ref), `fuel_type`(ref→fuel_types), `unit`(ref), `quantity`(number), `existence`(ref), `reporting_period`(FK)
`mobile_combustion` — `fuel_type`, `unit`, `quantity`, `existence`, `reporting_period`
`fugitive_emissions` — `system`(ref: refrigerant/fire/lab-gas), `gas_type`(ref→refrigerants|fire_suppressants), `unit`, `quantity`, `existence`
`consumables` — `material`(ref), `unit`, `quantity`, `existence`
`water_waste` — `type`(ref: consumption/waste), `unit`, `quantity`
`waste` — `type`(ref: disposal/treatment), `unit`, `quantity`
`leased_assets` — `asset`(ref: vehicles/office), `energy_type`(ref), `unit`, `quantity`
`commuting` — `commuter_type`(ref: student/employee), `unit`, `quantity`
`fertilizers` — `area_type`, `unit`, `quantity`
`capital_goods` — `asset_type`, `quantity`
`business_travel` — `ticket_type`, `quantity`

### C.6 Data Rows (DataRow) — volume

| Table | Rows |
|---|---|
| monthly_electricity | 30 |
| monthly_water | 18 |
| monthly_chilled_water | 26 |
| stationary_combustion | 11 |
| mobile_combustion | 3 |
| fugitive_emissions | 12 |
| consumables | 7 |
| water_waste | 2 |
| waste | 2 |
| leased_assets | 4 |
| commuting / fertilizers / capital_goods / business_travel | ~8 |
| **Total** | **~123 activity rows** |

### C.7 Emissions layer (calculation on top of activity data)

- **EmissionFactor** (global, NOT org-scoped): `EG_GRID_2024` (Scope 2 electricity), `EG_WATER_2024` (Scope 3 water), fuel factors (diesel/natural-gas/gasoline/LPG), refrigerant factors (via GWP), chilled-water factor, paper/waste factors.
- **GWP**: CO₂=1, CH₄, N₂O, R-134a (1430), R-410A (2088), R-407C (1774), SF₆ (23500) — AR5/AR6.
- **ReportingPeriod**: FY 2023-2024 (baseline), FY 2024-2025.
- **CalculationRule**: bind `total_kwh`/`total_m3`/`total_tr` and inventory `quantity` → factor (`rule_type='direct'`); `date_field=month` for time-series.
- **Calculation**: emitted rows carry `scope`, `category`, `co2e_kg`, `reporting_period`, `data_row` (lineage back to raw reading).
- **SBTiTarget / VerificationRecord**: targets + verify/review workflow.

---

## PART D — RESOLVED GAPS (user-provided Arabic translations)

### D.1 Campus identity — ANSWER: Excel = Smart Village only

**Numeric proof the Excel is Smart-Village-only, NOT combined:**
- Excel "2023-2024" sheet electricity = **2,704,187 kWh**.
- Excel "Detailed data" sheet total electricity = **2,704,187 kWh** (sum of buildings 401 + 2401 only).
- They match **exactly** → the summary sheet is derived from the Detailed sheet, which only meters buildings 401 + 2401 (Smart Village buildings).
- PDF page 2 = **Abu Qir campus alone** = **8,059,531 kWh** (FY 2025-26), ~3× the Excel total. If Excel were combined, it would be ≈ 11 M kWh, not 2.7 M.
- PDF pages 4–6 = **South Valley/Aswan branch** with its own distinct numbers (electricity 700,000 kWh, diesel 125,500 L, gasoline 3,680 L) — all different from Excel.

→ **Conclusion: Excel data = Smart Village campus only.** "Three campuses" is template text; only Smart Village (401 + 2401) was actually metered.

### D.2 PDF page 2 — Abu Qir electricity, FY 2025-26 (monthly kWh)

Title: *"Statement of total electricity consumption for the Academy buildings at Abu Qir campus, Alexandria, 01 Jul 2025 → 30 Jun 2026."* Rows = accounting months (NOT campuses):

| Month | kWh |
|---|---|
| Jul 2025 | 1,027,668 |
| Aug 2025 | 993,673 |
| Sep 2025 | 987,273 |
| Oct 2025 | 788,411 |
| Nov 2025 | 757,030 |
| Dec 2025 | 639,797 |
| Jan 2026 | 483,663 |
| Feb 2026 | 519,901 |
| Mar 2026 | 483,481 |
| Apr 2026 | 506,693 |
| May 2026 | 871,941 |
| Jun 2026 | *(blank)* |
| **Total** | **8,059,531** |

### D.3 PDF page 3 — Refrigerant cylinders (main campus + external sites), FY 2025-26

| # | Item (الصنف) | Qty | Notes |
|---|---|---|---|
| 1 | R22 | 25 | AC / package / DX units |
| 2 | R134a | 6 | Central AC — simulator bldg + Engineering G |
| 3 | R404A | 1 | Refrigeration/freezing rooms |
| 4 | R410A | 5 | VRV/VRF buildings |

### D.4 PDF page 4 — Cover letter: South Valley / Aswan branch (Finance Dept), FY 2025-26

### D.5 PDF page 5 — South Valley/Aswan, Scope 1 & 2 (FY 2025-26)

**Scope 1:** generators — diesel 25 m³; mobile — gasoline 3,680 L, diesel 125,500 L; fugitive — R-404A 25 kg, other 80 kg (fire suppressants mostly blank).
**Scope 2:** purchased electricity **700,000 kWh**; steam/heating/cooling blank.

### D.6 PDF page 6 — South Valley/Aswan, Scope 3 (FY 2025-26)

paper 137.5 ton, envelopes 550, ink 3,500, toner 30, ink-toner 15, soap 29,000, tissues 38,650, furniture 70, facilities 100, fertilizers 40, T&D losses 200,400, water 250,000, rented-vehicle fuel 220,000, rented-office electricity 960, rented-office water 200.

### D.7 PDF page 8 — Fuel consumption, Jul 2025 → Jun 2026 (South Valley/Aswan)

Columns: `Month | Gasoline 92 (L | EGP) | Gasoline 95 (L | EGP) | Diesel (L | EGP)` — monthly rows + total. (Financial + volumetric.)

### D.8 Chilled Water (TR) methodology — CONFIRMED

Chain: **TR·h → thermal kWh (×3.51685) → electrical kWh (÷ COP) → kgCO2e (× 0.4584 EG_GRID_2024)**.
Combined factor = `3.51685 / COP × 0.4584` kg CO2e per TR·h.
- COP 3.0 → 0.5374 kg/TR·h → 1,962,093.2 TR ≈ **1,054 t CO2e**
- COP 3.5 → 0.4606 kg/TR·h → ≈ **904 t CO2e**  *(default)*
- COP 4.0 → 0.4030 kg/TR·h → ≈ **791 t CO2e**

### D.9 Remaining open items
- `Pending ?` / `-` = treated as *not counted* (confirmed approach).
- Smart Village has **no refrigerant top-up data** (Excel lists R-134a/R-410A/R-407C but quantities `-`); the refrigerant data lives in PDF p3 (main campus = Smart Village? or Abu Qir?) — need attribution.
