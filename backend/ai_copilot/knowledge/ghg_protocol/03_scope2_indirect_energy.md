# Scope 2 Emissions: Indirect Energy Emissions

## Definition

Scope 2 emissions are indirect GHG emissions from the generation of purchased energy consumed by the reporting organization. These emissions physically occur at the facility where the energy is generated.

## Types of Purchased Energy

### 1. Purchased Electricity
The most common Scope 2 emission source:
- Grid electricity
- Directly purchased from generators
- Electricity from shared facilities

### 2. Purchased Steam
Steam purchased from external providers for:
- Industrial processes
- Space heating
- Power generation

### 3. Purchased Heating
Heat energy purchased from:
- District heating systems
- Combined heat and power (CHP) facilities
- Waste heat recovery systems

### 4. Purchased Cooling
Cooling purchased from:
- District cooling systems
- Chilled water providers

## Dual Reporting Requirement

The GHG Protocol Scope 2 Guidance requires companies to report using two methods:

### Location-Based Method
Reflects the average emissions intensity of the grid where energy consumption occurs:
- Uses grid-average emission factors
- Appropriate for national or regional grids
- Represents actual emissions at the point of consumption

**Example Calculation:**
```
Emissions = Electricity (kWh) × Grid Emission Factor (kg CO2e/kWh)
```

### Market-Based Method
Reflects emissions from specific energy purchasing choices:
- Uses supplier-specific emission factors
- Accounts for renewable energy certificates (RECs)
- Reflects power purchase agreements (PPAs)

**Contractual Instruments (in hierarchy order):**
1. Energy attribute certificates (RECs, GOs, I-RECs)
2. Direct contracts (PPAs) with specific suppliers
3. Supplier-specific emission factors
4. Residual mix emission factors
5. Grid-average factors (fallback)

## Grid Emission Factors by Region (Examples)

| Country/Region | Factor (kg CO2e/kWh) | Year |
|----------------|---------------------|------|
| United Kingdom | 0.233 | 2023 |
| United States (avg) | 0.417 | 2023 |
| Germany | 0.366 | 2023 |
| France | 0.058 | 2023 |
| China | 0.581 | 2023 |
| India | 0.708 | 2023 |
| Australia | 0.680 | 2023 |
| Brazil | 0.067 | 2023 |
| Japan | 0.434 | 2023 |
| Canada | 0.120 | 2023 |

## Renewable Energy and Scope 2

### Zero-Emission Sources
The following may claim zero Scope 2 emissions (market-based):
- Solar (photovoltaic)
- Wind power
- Hydroelectric
- Geothermal
- Nuclear (low-carbon, though not renewable)

### Renewable Energy Certificates (RECs)
- Must be unbundled or bundled with electricity
- One REC typically = 1 MWh of renewable generation
- Must meet Scope 2 Quality Criteria:
  - Be the only instrument conveying the emission rate claim
  - Be issued as close as possible to energy generation
  - Be retired within the reporting period

### Power Purchase Agreements (PPAs)
Types of PPAs:
1. **Physical PPA**: Direct delivery of renewable electricity
2. **Virtual PPA (VPPA)**: Financial agreement without physical delivery
3. **Sleeved PPA**: Third-party manages grid delivery

## Calculating Scope 2 Emissions

### Step 1: Collect Energy Data
- Utility bills and invoices
- Meter readings
- Building energy management data
- Landlord-provided data (for leased spaces)

### Step 2: Organize by Location
Group consumption data by:
- Country/region (for grid factors)
- Specific facilities
- Contract type (for market-based)

### Step 3: Apply Emission Factors

**Location-Based:**
```
Emissions = kWh consumed × Regional grid factor
```

**Market-Based:**
```
Emissions = (Total kWh - Renewable kWh) × Supplier factor
         + Renewable kWh × 0 (if certified)
```

### Step 4: Report Both Methods
Include in reports:
- Total Scope 2 (location-based)
- Total Scope 2 (market-based)
- Description of contractual instruments

## Best Practices

### Data Collection
1. Obtain actual meter data where possible
2. Use estimation methods for gaps (degree-day analysis, occupancy rates)
3. Document all data sources and methodologies
4. Verify landlord-provided data

### Emission Factor Selection
1. Use most current factors available
2. Apply regional factors where available (not national averages)
3. For market-based, prioritize supplier-specific data
4. Document factor sources and dates

### Renewable Energy Claims
1. Verify certificates are retired and not double-counted
2. Match certificates to reporting period
3. Maintain documentation for verification
4. Consider additionality for maximum impact

## T&D Losses

Transmission and distribution (T&D) losses should be included:
- Occur between generation and consumption
- Typically 5-15% of delivered electricity
- Often included in published grid factors
- If not, calculate: `Losses = Consumption × T&D Loss Factor`

## Common Challenges

### Leased Buildings
- Obtain data from landlords
- Use LEED/BREEAM benchmarks if data unavailable
- Consider sub-metering for accuracy

### Data Gaps
- Use estimation methods (area-based, headcount-based)
- Apply conservative factors
- Disclose estimation methodology

### Multiple Locations
- Maintain location-specific tracking
- Apply appropriate regional factors
- Consider software solutions for complex portfolios
