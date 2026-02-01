# GHG Calculation Methodology

## Overview

This document provides detailed guidance on calculating greenhouse gas emissions according to the GHG Protocol methodology.

## Basic Calculation Formula

The fundamental equation for GHG calculation:

```
GHG Emissions (kg CO2e) = Activity Data × Emission Factor × Global Warming Potential
```

**Components:**
- **Activity Data**: Quantity of the emission-generating activity
- **Emission Factor**: Emissions per unit of activity
- **Global Warming Potential (GWP)**: Conversion factor to CO2 equivalent

## Global Warming Potentials (GWPs)

GWPs convert different greenhouse gases to CO2 equivalents. Use consistent GWP values (AR5 or AR6 recommended).

### Key GWPs (IPCC AR6, 100-year horizon)

| Gas | Chemical Formula | GWP-100 |
|-----|-----------------|---------|
| Carbon Dioxide | CO2 | 1 |
| Methane | CH4 | 29.8 |
| Nitrous Oxide | N2O | 273 |
| HFC-32 | CH2F2 | 771 |
| HFC-134a | CH2FCF3 | 1,530 |
| HFC-410A | R-410A | 2,256 |
| PFC-14 | CF4 | 7,380 |
| Sulfur Hexafluoride | SF6 | 25,200 |
| Nitrogen Trifluoride | NF3 | 17,400 |

### AR5 vs AR6 GWPs
- AR5 (2014): Widely used, accepted by most standards
- AR6 (2021): Latest values, higher CH4 GWP
- Be consistent within reporting period

## Calculation Methods by Source

### Stationary Combustion

**Tier 1 (Fuel-Based):**
```
CO2 = Fuel Consumed × CO2 Emission Factor
CH4 = Fuel Consumed × CH4 Emission Factor  
N2O = Fuel Consumed × N2O Emission Factor
Total CO2e = CO2 + (CH4 × GWP_CH4) + (N2O × GWP_N2O)
```

**Example - Natural Gas:**
```
Fuel = 100,000 kWh (gross CV)
CO2 factor = 0.184 kg/kWh
CH4 factor = 0.00035 kg/kWh
N2O factor = 0.00003 kg/kWh

CO2 = 100,000 × 0.184 = 18,400 kg
CH4 = 100,000 × 0.00035 = 35 kg → 35 × 29.8 = 1,043 kg CO2e
N2O = 100,000 × 0.00003 = 3 kg → 3 × 273 = 819 kg CO2e

Total = 18,400 + 1,043 + 819 = 20,262 kg CO2e
```

### Mobile Combustion

**Method 1: Fuel-Based**
```
Emissions = Fuel Volume × Emission Factor
```

**Example - Diesel Vehicle:**
```
Diesel = 5,000 liters
Emission factor = 2.68 kg CO2e/liter

Emissions = 5,000 × 2.68 = 13,400 kg CO2e
```

**Method 2: Distance-Based**
```
Emissions = Distance × Emission Factor per km
```

**Example - Company Car:**
```
Distance = 25,000 km
Vehicle = Medium diesel car (0.168 kg CO2e/km)

Emissions = 25,000 × 0.168 = 4,200 kg CO2e
```

### Electricity (Scope 2)

**Location-Based:**
```
Emissions = Electricity (kWh) × Grid Factor
```

**Example:**
```
Electricity = 500,000 kWh
UK Grid Factor = 0.233 kg CO2e/kWh

Emissions = 500,000 × 0.233 = 116,500 kg CO2e
```

**Market-Based with RECs:**
```
Total electricity = 500,000 kWh
RECs purchased = 300,000 kWh
Remaining = 200,000 kWh

Emissions = 200,000 × Supplier Factor
         + 300,000 × 0 (certified renewable)
```

### Refrigerant Leakage

**Screening Method:**
```
Emissions = Equipment Capacity × Assumed Leak Rate × GWP
```

**Mass Balance Method (Preferred):**
```
Emissions = (Beginning Inventory + Purchases - Ending Inventory) × GWP
```

**Example:**
```
Beginning inventory R-410A = 50 kg
Purchases = 20 kg
Ending inventory = 45 kg
GWP R-410A = 2,256

Leakage = 50 + 20 - 45 = 25 kg
Emissions = 25 × 2,256 = 56,400 kg CO2e
```

### Business Travel (Scope 3)

**Air Travel:**
```
Emissions = Distance × Passengers × Emission Factor × Uplift Factor
```

**Uplift Factor:** Accounts for non-direct routes (typically 1.09)

**With Radiative Forcing:**
```
Emissions = CO2 Emissions × Radiative Forcing Multiplier (1.9-2.7)
```

**Example:**
```
Flight: London to New York (5,570 km one-way)
Class: Economy
Passengers: 1
Round trip factor: 2

Base factor = 0.148 kg CO2e/km
Emissions = 5,570 × 2 × 1 × 0.148 × 1.09 = 1,797 kg CO2e
With RF (×1.9) = 3,415 kg CO2e
```

### Purchased Goods (Scope 3)

**Spend-Based:**
```
Emissions = Spend (currency) × EIO Factor (kg CO2e/currency unit)
```

**Activity-Based:**
```
Emissions = Quantity × Cradle-to-Gate Emission Factor
```

**Example - Office Paper:**
```
Paper purchased = 10 tonnes
Emission factor = 919 kg CO2e/tonne (virgin paper)

Emissions = 10 × 919 = 9,190 kg CO2e
```

### Waste (Scope 3)

```
Emissions = Waste Mass × Disposal Factor
```

**Example:**
```
Landfill waste = 50 tonnes
Recycled paper = 20 tonnes

Landfill emissions = 50 × 579 = 28,950 kg CO2e
Recycling emissions = 20 × 21 = 420 kg CO2e
Total = 29,370 kg CO2e
```

## Unit Conversions

### Energy Units
| From | To | Multiply by |
|------|-----|-------------|
| kWh | MJ | 3.6 |
| therms | kWh | 29.3 |
| GJ | kWh | 277.78 |
| MMBTU | kWh | 293.07 |

### Volume Units
| From | To | Multiply by |
|------|-----|-------------|
| gallons (US) | liters | 3.785 |
| gallons (UK) | liters | 4.546 |
| barrels (oil) | liters | 158.99 |
| cubic feet | cubic meters | 0.0283 |

### Mass Units
| From | To | Multiply by |
|------|-----|-------------|
| short tons | metric tonnes | 0.907 |
| long tons | metric tonnes | 1.016 |
| pounds | kg | 0.454 |

## Data Quality Assessment

### Quality Indicators

1. **Temporal representativeness**: Age of data
2. **Geographical representativeness**: Regional relevance
3. **Technological representativeness**: Process similarity
4. **Completeness**: Coverage of all sources
5. **Reliability**: Verification status

### Uncertainty Management

- Use ranges where exact data unavailable
- Apply Monte Carlo simulation for complex estimates
- Document assumptions and limitations
- Prioritize improvement of high-uncertainty, material sources

## Validation Checks

1. **Year-over-year comparison**: Flag significant changes
2. **Intensity metrics**: Emissions per revenue, FTE, production
3. **Benchmarking**: Compare to industry peers
4. **Reasonableness checks**: Verify calculations mathematically
5. **Completeness review**: Ensure all sources captured
