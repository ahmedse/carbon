# AASTMT Carbon Platform - Complete Deployment Plan

**Target Organization:** Arab Academy for Science, Technology & Maritime Transport  
**Domain:** Carbon Emissions Management (GHG Protocol)  
**Date:** 2026-07-25  
**Purpose:** Production-ready Carbon system deployment with realistic organizational structure

---

## 1. Organizational Structure (OrgUnits)

### Carbon-Relevant Organizational Units

```yaml
AASTMT_ORG_STRUCTURE:
  - id: aastmt_campus
    name: "AASTMT Smart Village Campus"
    code: "AASTMT-SV"
    type: campus
    parent: null
    description: "Main campus with all facilities"
    
  - id: facilities_dept
    name: "Facilities Management Department"
    code: "FAC-MGMT"
    type: department
    parent: aastmt_campus
    description: "Manages all buildings, utilities, and infrastructure"
    
  - id: transport_fleet
    name: "Transportation & Fleet Management"
    code: "TRANS-FLEET"
    type: department
    parent: aastmt_campus
    description: "University buses, service vehicles, staff transport"
    
  - id: energy_utilities
    name: "Energy & Utilities Department"
    code: "ENERGY-UTIL"
    type: department
    parent: aastmt_campus
    description: "Electricity, water, gas, HVAC systems"
    
  - id: procurement_dept
    name: "Procurement Department"
    code: "PROCURE"
    type: department
    parent: aastmt_campus
    description: "Purchasing, vendor management, supply chain"
    
  - id: it_infrastructure
    name: "IT Infrastructure"
    code: "IT-INFRA"
    type: department
    parent: aastmt_campus
    description: "Data centers, servers, network equipment"
    
  - id: research_labs
    name: "Research Labs & Centers"
    code: "RES-LABS"
    type: department
    parent: aastmt_campus
    description: "Engineering labs, maritime research, specialized equipment"
```

---

## 2. Master Data & Reference Sets

### Reference Set 1: Building Types
```yaml
reference_set: building_types
code: BLDG_TYPE
description: "Types of campus buildings for energy allocation"
values:
  - code: ADM
    label: Administrative Building
    description: "Offices, meeting rooms, administrative functions"
    
  - code: ACD
    label: Academic Building
    description: "Classrooms, lecture halls"
    
  - code: LAB
    label: Laboratory Building
    description: "Engineering labs, research facilities"
    
  - code: LIB
    label: Library
    description: "Central library and study areas"
    
  - code: DORM
    label: Dormitory
    description: "Student housing"
    
  - code: CAFE
    label: Cafeteria/Dining
    description: "Food service facilities"
    
  - code: SPORT
    label: Sports Facilities
    description: "Gyms, sports halls, fields"
    
  - code: MAINT
    label: Maintenance & Storage
    description: "Workshops, storage, utilities"
```

### Reference Set 2: Vehicle Types
```yaml
reference_set: vehicle_types
code: VEH_TYPE
description: "University fleet vehicle classifications"
values:
  - code: BUS-LARGE
    label: Large Bus (50+ seats)
    description: "Student shuttle buses"
    
  - code: BUS-MINI
    label: Minibus (20-30 seats)
    description: "Staff and small group transport"
    
  - code: CAR-SEDAN
    label: Sedan Car
    description: "Administrative vehicles"
    
  - code: VAN-CARGO
    label: Cargo Van
    description: "Delivery and maintenance"
    
  - code: TRUCK-SMALL
    label: Small Truck
    description: "Equipment and waste transport"
    
  - code: MAINT-VEH
    label: Maintenance Vehicle
    description: "Specialized maintenance equipment"
```

### Reference Set 3: Fuel Types
```yaml
reference_set: fuel_types
code: FUEL_TYPE
description: "Fuel types used across campus operations"
values:
  - code: DIESEL
    label: Diesel Fuel
    unit: liters
    emission_factor: 2.68  # kg CO2e per liter
    
  - code: GASOLINE
    label: Gasoline (Petrol)
    unit: liters
    emission_factor: 2.31  # kg CO2e per liter
    
  - code: NATURAL_GAS
    label: Natural Gas
    unit: cubic_meters
    emission_factor: 2.03  # kg CO2e per m³
    
  - code: LPG
    label: Liquefied Petroleum Gas
    unit: kg
    emission_factor: 3.00  # kg CO2e per kg
    
  - code: GRID_ELEC
    label: Grid Electricity
    unit: kWh
    emission_factor: 0.527  # kg CO2e per kWh (Egypt grid)
```

### Reference Set 4: Energy Sources
```yaml
reference_set: energy_sources
code: ENERGY_SRC
description: "Energy sources for campus consumption"
values:
  - code: GRID_MAIN
    label: Main Grid Supply
    scope: 2
    
  - code: SOLAR_PV
    label: Solar Photovoltaic
    scope: renewable
    
  - code: DIESEL_GEN
    label: Diesel Generator Backup
    scope: 1
    
  - code: UPS_BATTERY
    label: UPS Battery Systems
    scope: equipment
```

### Reference Set 5: Emission Categories
```yaml
reference_set: emission_categories
code: EMIS_CAT
description: "GHG Protocol emission categories"
values:
  - code: STATIONARY_COMB
    label: Stationary Combustion
    scope: 1
    description: "Boilers, furnaces, generators"
    
  - code: MOBILE_COMB
    label: Mobile Combustion
    scope: 1
    description: "Fleet vehicles, equipment"
    
  - code: FUGITIVE_EMIS
    label: Fugitive Emissions
    scope: 1
    description: "Refrigerants, AC leaks"
    
  - code: PURCHASED_ELEC
    label: Purchased Electricity
    scope: 2
    description: "Grid electricity consumption"
    
  - code: BUSINESS_TRAVEL
    label: Business Travel
    scope: 3
    description: "Staff/student travel not in fleet"
    
  - code: WASTE
    label: Waste Disposal
    scope: 3
    description: "Solid waste, wastewater"
    
  - code: PROCUREMENT
    label: Purchased Goods
    scope: 3
    description: "Embodied emissions in purchases"
```

---

## 3. Data Products (Modules)

### Module 1: Scope 1 - Direct Emissions
```yaml
module:
  name: "AASTMT Scope 1 Emissions"
  code: "CARBON-S1"
  org_unit: aastmt_campus
  scope: 1
  description: "Direct GHG emissions from sources owned/controlled by AASTMT"
  owner: facilities_dept
  
  data_tables:
    - name: "Fleet Fuel Consumption"
      code: "S1_FLEET_FUEL"
      description: "Daily fuel consumption by university vehicles"
      
    - name: "Generator Fuel Consumption"
      code: "S1_GEN_FUEL"
      description: "Backup generator diesel consumption"
      
    - name: "Refrigerant Leakage"
      code: "S1_REFRIG"
      description: "HVAC and refrigeration gas leaks/refills"
```

### Module 2: Scope 2 - Electricity
```yaml
module:
  name: "AASTMT Scope 2 Emissions"
  code: "CARBON-S2"
  org_unit: aastmt_campus
  scope: 2
  description: "Indirect GHG emissions from purchased electricity"
  owner: energy_utilities
  
  data_tables:
    - name: "Building Electricity Consumption"
      code: "S2_BLDG_ELEC"
      description: "Monthly electricity readings per building"
      
    - name: "Equipment Energy Consumption"
      code: "S2_EQUIP_ELEC"
      description: "Energy consumption by major equipment (HVAC, chillers, servers)"
```

### Module 3: Scope 3 - Other Indirect
```yaml
module:
  name: "AASTMT Scope 3 Emissions"
  code: "CARBON-S3"
  org_unit: aastmt_campus
  scope: 3
  description: "Other indirect GHG emissions from value chain"
  owner: procurement_dept
  
  data_tables:
    - name: "Business Travel Records"
      code: "S3_TRAVEL"
      description: "Staff/faculty business travel emissions"
      
    - name: "Waste Disposal Records"
      code: "S3_WASTE"
      description: "Solid waste and recycling tracking"
      
    - name: "Water Consumption"
      code: "S3_WATER"
      description: "Water supply and wastewater treatment"
```

---

## 4. Data Table Schemas

### Table: Fleet Fuel Consumption (S1_FLEET_FUEL)

```yaml
table_schema:
  name: Fleet Fuel Consumption
  code: S1_FLEET_FUEL
  module: CARBON-S1
  
  fields:
    - name: record_date
      type: date
      required: true
      description: "Date of fuel transaction"
      
    - name: vehicle_id
      type: text
      required: true
      description: "Vehicle plate/identification number"
      
    - name: vehicle_type
      type: reference
      reference_set: vehicle_types
      required: true
      
    - name: fuel_type
      type: reference
      reference_set: fuel_types
      required: true
      
    - name: fuel_quantity
      type: decimal
      required: true
      unit: liters
      description: "Fuel quantity consumed"
      
    - name: odometer_reading
      type: integer
      unit: km
      description: "Vehicle odometer at time of refuel"
      
    - name: department
      type: reference
      reference_set: org_units
      description: "Department using the vehicle"
      
    - name: driver_name
      type: text
      description: "Driver or responsible person"
      
    - name: notes
      type: text
      description: "Additional details (route, purpose, etc.)"
```

### Table: Building Electricity Consumption (S2_BLDG_ELEC)

```yaml
table_schema:
  name: Building Electricity Consumption
  code: S2_BLDG_ELEC
  module: CARBON-S2
  
  fields:
    - name: billing_month
      type: date
      required: true
      description: "Billing period (first day of month)"
      
    - name: building_code
      type: text
      required: true
      description: "Building identifier (B1, B2, etc.)"
      
    - name: building_type
      type: reference
      reference_set: building_types
      required: true
      
    - name: meter_number
      type: text
      required: true
      description: "Utility meter number"
      
    - name: previous_reading
      type: decimal
      required: true
      unit: kWh
      description: "Previous meter reading"
      
    - name: current_reading
      type: decimal
      required: true
      unit: kWh
      description: "Current meter reading"
      
    - name: consumption
      type: decimal
      required: true
      unit: kWh
      description: "Consumption (current - previous)"
      
    - name: cost
      type: decimal
      unit: EGP
      description: "Electricity cost for period"
      
    - name: verified_by
      type: text
      description: "Staff member who verified reading"
```

### Table: Business Travel Records (S3_TRAVEL)

```yaml
table_schema:
  name: Business Travel Records
  code: S3_TRAVEL
  module: CARBON-S3
  
  fields:
    - name: travel_date
      type: date
      required: true
      description: "Date of travel"
      
    - name: employee_name
      type: text
      required: true
      description: "Traveler name"
      
    - name: department
      type: reference
      reference_set: org_units
      required: true
      
    - name: origin
      type: text
      required: true
      description: "Origin city/location"
      
    - name: destination
      type: text
      required: true
      description: "Destination city/location"
      
    - name: travel_mode
      type: text
      required: true
      description: "Flight, Train, Car, etc."
      
    - name: distance_km
      type: decimal
      required: true
      unit: km
      description: "Total distance traveled"
      
    - name: purpose
      type: text
      description: "Purpose of travel (conference, meeting, etc.)"
```

---

## 5. Users & Scoped Roles

### User Definitions

```yaml
users:
  - username: ahmed
    email: ahmed@aastmt.edu.eg
    role: Platform Administrator
    is_superuser: true
    password: AdminPa_132  # existing
    
  - username: ali
    email: ali.hassan@aastmt.edu.eg
    first_name: Ali
    last_name: Hassan
    role: Carbon Analyst
    password: Ali2026!
    
  - username: fatima_facilities
    email: fatima.ahmed@aastmt.edu.eg
    first_name: Fatima
    last_name: Ahmed
    role: Facilities Data Owner
    password: Fatima2026!
    
  - username: mohammed_transport
    email: mohammed.omar@aastmt.edu.eg
    first_name: Mohammed
    last_name: Omar
    role: Transportation Data Owner
    password: Mohammed2026!
    
  - username: sarah_analyst
    email: sarah.mohamed@aastmt.edu.eg
    first_name: Sarah
    last_name: Mohamed
    role: Carbon Analyst
    password: Sarah2026!
    
  - username: youssef_energy
    email: youssef.ibrahim@aastmt.edu.eg
    first_name: Youssef
    last_name: Ibrahim
    role: Energy Data Entry
    password: Youssef2026!
    
  - username: layla_auditor
    email: layla.zaki@aastmt.edu.eg
    first_name: Layla
    last_name: Zaki
    role: Carbon Auditor
    password: Layla2026!
```

### Scoped Role Assignments

```yaml
scoped_roles:
  # Platform Admin (Global)
  - user: ahmed
    group: admins_group
    org_unit: null
    module: null
    scope: global
    description: "Full platform access"
    
  # Carbon Domain Admin (Global Carbon)
  - user: ali
    group: carbon_admin
    org_unit: null
    module: null
    scope: global
    description: "Carbon domain administrator"
    
  # Facilities Data Owner (Scope 1 + Scope 2 modules)
  - user: fatima_facilities
    group: dataowners_group
    org_unit: facilities_dept
    module: CARBON-S1
    scope: module
    description: "Owns Scope 1 data for facilities"
    
  - user: fatima_facilities
    group: dataowners_group
    org_unit: facilities_dept
    module: CARBON-S2
    scope: module
    description: "Owns Scope 2 data for facilities"
    
  # Transportation Data Owner (Scope 1 fleet)
  - user: mohammed_transport
    group: dataowners_group
    org_unit: transport_fleet
    module: CARBON-S1
    scope: module
    description: "Owns fleet fuel data"
    
  # Energy Data Entry (Scope 2 only, read/write)
  - user: youssef_energy
    group: data_entry
    org_unit: energy_utilities
    module: CARBON-S2
    scope: module
    description: "Enters electricity consumption data"
    
  # Carbon Analyst (Read all carbon modules)
  - user: sarah_analyst
    group: analysts_group
    org_unit: aastmt_campus
    module: CARBON-S1
    scope: module
    
  - user: sarah_analyst
    group: analysts_group
    org_unit: aastmt_campus
    module: CARBON-S2
    scope: module
    
  - user: sarah_analyst
    group: analysts_group
    org_unit: aastmt_campus
    module: CARBON-S3
    scope: module
    
  # Carbon Auditor (Read-only, all scopes)
  - user: layla_auditor
    group: auditors_group
    org_unit: aastmt_campus
    module: CARBON-S1
    scope: module
    
  - user: layla_auditor
    group: auditors_group
    org_unit: aastmt_campus
    module: CARBON-S2
    scope: module
    
  - user: layla_auditor
    group: auditors_group
    org_unit: aastmt_campus
    module: CARBON-S3
    scope: module
```

---

## 6. Sample Data (Realistic 2026 Data)

### Fleet Fuel - January 2026 (10 sample records)

```csv
record_date,vehicle_id,vehicle_type,fuel_type,fuel_quantity,odometer_reading,department,driver_name,notes
2026-01-05,BUS-001,BUS-LARGE,DIESEL,180.5,45230,transport_fleet,Ahmed Mahmoud,Student shuttle - Smart Village to Maadi route
2026-01-05,BUS-002,BUS-LARGE,DIESEL,175.2,38120,transport_fleet,Hassan Ali,Morning student transport
2026-01-06,CAR-ADM-01,CAR-SEDAN,GASOLINE,45.0,12350,facilities_dept,Fatima Ahmed,Administrative errands
2026-01-07,VAN-001,VAN-CARGO,DIESEL,52.3,28450,facilities_dept,Mohamed Omar,Equipment delivery to labs
2026-01-08,BUS-003,BUS-MINI,DIESEL,68.0,22100,transport_fleet,Ibrahim Khalil,Staff transport
2026-01-10,BUS-001,BUS-LARGE,DIESEL,185.0,45620,transport_fleet,Ahmed Mahmoud,Weekend student events
2026-01-12,TRUCK-01,TRUCK-SMALL,DIESEL,95.5,19800,facilities_dept,Youssef Ibrahim,Waste removal and recycling
2026-01-14,CAR-ADM-02,CAR-SEDAN,GASOLINE,42.0,8920,procurement_dept,Sarah Mohamed,Vendor meetings
2026-01-15,BUS-002,BUS-LARGE,DIESEL,178.8,38510,transport_fleet,Hassan Ali,Daily student route
2026-01-18,VAN-002,VAN-CARGO,DIESEL,48.5,15600,it_infrastructure,Omar Zaki,Equipment transport to data center
```

### Building Electricity - January 2026 (8 buildings)

```csv
billing_month,building_code,building_type,meter_number,previous_reading,current_reading,consumption,cost,verified_by
2026-01-01,B1,ADM,MTR-001,245680,268930,23250,45870.00,Youssef Ibrahim
2026-01-01,B2,ACD,MTR-002,189450,208720,19270,38003.00,Youssef Ibrahim
2026-01-01,B3,LAB,MTR-003,312580,348920,36340,71670.80,Fatima Ahmed
2026-01-01,B4,LIB,MTR-004,156890,172340,15450,30487.00,Youssef Ibrahim
2026-01-01,B5,CAFE,MTR-005,98750,112890,14140,27896.00,Sarah Mohamed
2026-01-01,B6,DORM,MTR-006,523400,578920,55520,109526.40,Youssef Ibrahim
2026-01-01,B7,SPORT,MTR-007,78920,89650,10730,21159.00,Fatima Ahmed
2026-01-01,DC-01,IT-INFRA,MTR-008,456780,498920,42140,83116.00,Omar Zaki
```

### Business Travel - January 2026 (5 trips)

```csv
travel_date,employee_name,department,origin,destination,travel_mode,distance_km,purpose
2026-01-10,Dr. Ahmed Hassan,research_labs,Cairo,Dubai,Flight,2400,Maritime Research Conference
2026-01-15,Prof. Layla Mohamed,research_labs,Cairo,Alexandria,Train,220,Collaboration meeting with Alexandria University
2026-01-20,Dr. Sarah Ibrahim,procurement_dept,Cairo,London,Flight,5600,Equipment procurement negotiations
2026-01-22,Eng. Mohamed Zaki,it_infrastructure,Cairo,Riyadh,Flight,2800,Data center technology seminar
2026-01-25,Dr. Fatima Omar,facilities_dept,Cairo,Sharm El Sheikh,Flight,800,Sustainability workshop
```

---

## 7. Emission Factors (Egypt Context)

```yaml
emission_factors:
  # Scope 1 - Fuels
  diesel:
    value: 2.68
    unit: kg CO2e per liter
    source: "DEFRA 2025 / Egypt Carbon Registry"
    
  gasoline:
    value: 2.31
    unit: kg CO2e per liter
    source: "DEFRA 2025"
    
  natural_gas:
    value: 2.03
    unit: kg CO2e per m³
    source: "IPCC Guidelines 2024"
    
  # Scope 2 - Electricity
  grid_electricity_egypt:
    value: 0.527
    unit: kg CO2e per kWh
    source: "Egyptian Electricity Holding Company 2025"
    description: "Egypt national grid emission factor"
    
  # Scope 3 - Travel
  air_travel_short:
    value: 0.156
    unit: kg CO2e per passenger-km
    description: "Flights < 1500 km"
    
  air_travel_long:
    value: 0.103
    unit: kg CO2e per passenger-km
    description: "Flights > 1500 km"
    
  rail_travel:
    value: 0.041
    unit: kg CO2e per passenger-km
    
  waste_landfill:
    value: 0.580
    unit: kg CO2e per kg waste
```

---

## 8. Expected Carbon Results (January 2026)

### Scope 1 - Fleet Emissions
- **Total Fuel Consumed:** ~1,118 liters diesel + 87 liters gasoline
- **Estimated CO2e:** (1118 × 2.68) + (87 × 2.31) = **3,197 kg CO2e**

### Scope 2 - Electricity Emissions
- **Total Consumption:** 216,840 kWh
- **Estimated CO2e:** 216,840 × 0.527 = **114,275 kg CO2e**

### Scope 3 - Business Travel
- **Total Distance:** 11,820 km (mostly flights)
- **Estimated CO2e:** ~1,250 kg CO2e

### Total Campus Emissions (Jan 2026)
**~118.7 tons CO2e**

---

## 9. Deployment Execution Steps

### Phase 1: Infrastructure Setup
```bash
# 1. Create organizational units
python manage.py shell < scripts/deploy_orgunits.py

# 2. Create reference sets
python manage.py shell < scripts/deploy_references.py

# 3. Create data products (modules)
python manage.py shell < scripts/deploy_modules.py
```

### Phase 2: Schema Setup
```bash
# 4. Create data tables with schemas
python manage.py shell < scripts/deploy_tables.py

# 5. Seed emission factors
python manage.py seed_emission_factors
```

### Phase 3: User & Access Setup
```bash
# 6. Create users
python manage.py shell < scripts/deploy_users.py

# 7. Create groups
python manage.py shell < scripts/deploy_groups.py

# 8. Assign scoped roles
python manage.py shell < scripts/deploy_scoped_roles.py
```

### Phase 4: Sample Data
```bash
# 9. Load sample data (January 2026)
python manage.py shell < scripts/deploy_sample_data.py

# 10. Run initial calculations
python manage.py shell < scripts/calculate_emissions.py
```

### Phase 5: Verification
```bash
# 11. Verify deployment
python manage.py shell < scripts/verify_deployment.py

# Expected output:
# ✓ 7 OrgUnits created
# ✓ 5 Reference Sets with 32 values
# ✓ 3 Modules (S1, S2, S3)
# ✓ 6 Data Tables with schemas
# ✓ 7 Users created
# ✓ 14 Scoped role assignments
# ✓ 23 sample data rows
# ✓ Estimated emissions: 118.7 tons CO2e
```

---

## 10. Login Credentials Summary

```
Platform Administrator:
  username: ahmed
  password: AdminPa_132
  access: Full platform + all modules

Carbon Domain Admin:
  username: ali
  password: Ali2026!
  access: All carbon modules (admin level)

Facilities Data Owner:
  username: fatima_facilities
  password: Fatima2026!
  access: Scope 1 & 2 modules (facilities org unit)

Transportation Data Owner:
  username: mohammed_transport
  password: Mohammed2026!
  access: Scope 1 module (transport fleet)

Energy Data Entry:
  username: youssef_energy
  password: Youssef2026!
  access: Scope 2 module (data entry only)

Carbon Analyst:
  username: sarah_analyst
  password: Sarah2026!
  access: All carbon modules (read + analyze)

Carbon Auditor:
  username: layla_auditor
  password: Layla2026!
  access: All carbon modules (read-only, verification)
```

---

## 11. Next Steps After Deployment

1. **Train Data Owners:** Fatima (facilities), Mohammed (transport), Youssef (energy)
2. **Configure DQ Rules:** Completeness, validity ranges, cross-checks
3. **Set up Dashboards:** Carbon owner portal, analyst views
4. **Monthly Reporting:** Configure automated monthly emission reports
5. **Audit Trail:** Enable governance events for all data changes
6. **Expand Scope 3:** Add procurement, waste, water consumption data
7. **Historical Data:** Load 2024-2025 data for trend analysis
8. **Mobile App:** Enable mobile data entry for field readings

---

## 12. Future Domain Expansions

Once Carbon is stable, apply the same pattern to other domains:

- **Academic KPIs Domain**
  - OrgUnits: Colleges, departments, programs
  - Modules: Student performance, faculty metrics, research output
  - Roles: Dean, department head, academic coordinator

- **Research Output Domain**
  - OrgUnits: Research centers, labs
  - Modules: Publications, grants, patents
  - Roles: Research admin, PI, coordinator

- **Financial Performance Domain**
  - OrgUnits: Cost centers, budget units
  - Modules: Revenue, expenses, allocations
  - Roles: Finance admin, budget owner, analyst

**Pattern:** OrgUnits → Master Data → Modules → Tables → Users → Roles → Data → Analytics

---

**END OF DEPLOYMENT PLAN**
