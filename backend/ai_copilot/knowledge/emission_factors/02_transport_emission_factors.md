# Vehicle and Transport Emission Factors

## Overview

This document provides emission factors for various modes of transportation, including road vehicles, rail, aviation, and shipping.

## Road Transport Emission Factors

### Passenger Vehicles by Size

#### Petrol/Gasoline Cars

| Size Category | Engine (L) | kg CO2e/km | kg CO2e/mile |
|---------------|------------|------------|--------------|
| Small | <1.4 | 0.149 | 0.240 |
| Medium | 1.4-2.0 | 0.178 | 0.286 |
| Large | >2.0 | 0.278 | 0.447 |
| Average | - | 0.174 | 0.280 |

#### Diesel Cars

| Size Category | Engine (L) | kg CO2e/km | kg CO2e/mile |
|---------------|------------|------------|--------------|
| Small | <1.7 | 0.140 | 0.225 |
| Medium | 1.7-2.0 | 0.168 | 0.270 |
| Large | >2.0 | 0.209 | 0.336 |
| Average | - | 0.171 | 0.275 |

#### Hybrid Cars

| Type | kg CO2e/km | kg CO2e/mile |
|------|------------|--------------|
| Hybrid (petrol) | 0.120 | 0.193 |
| Plug-in hybrid | 0.071 | 0.114 |
| Battery EV* | 0.000 | 0.000 |

*Direct tailpipe emissions only; electricity Scope 2 reported separately

#### Electric Vehicles (Lifecycle)

Including electricity generation (UK grid 2023):
| Vehicle Type | kg CO2e/km |
|--------------|------------|
| Small BEV | 0.046 |
| Medium BEV | 0.053 |
| Large BEV | 0.061 |

### Commercial Vehicles

#### Vans

| Size | Fuel | kg CO2e/km | kg CO2e/mile |
|------|------|------------|--------------|
| Small van | Petrol | 0.205 | 0.330 |
| Small van | Diesel | 0.169 | 0.272 |
| Medium van | Diesel | 0.195 | 0.314 |
| Large van | Diesel | 0.248 | 0.399 |

#### Heavy Goods Vehicles (HGVs)

| Type | Max Weight | kg CO2e/km | kg CO2e/tonne-km |
|------|------------|------------|------------------|
| Rigid | ≤7.5t | 0.491 | 0.655 |
| Rigid | 7.5-17t | 0.600 | 0.188 |
| Rigid | >17t | 0.857 | 0.119 |
| Articulated | ≤33t | 0.802 | 0.070 |
| Articulated | >33t | 0.926 | 0.048 |

**Average load factors used:**
- Rigid trucks: 50% capacity utilization
- Articulated trucks: 60% capacity utilization

### Motorcycles

| Engine Size | kg CO2e/km |
|-------------|------------|
| <125cc | 0.084 |
| 125-500cc | 0.100 |
| >500cc | 0.133 |

## Rail Transport

### Passenger Rail

| Type | kg CO2e/passenger-km |
|------|---------------------|
| National rail | 0.035 |
| Light rail/tram | 0.029 |
| London Underground | 0.028 |
| International rail | 0.004 |
| Eurostar | 0.003 |

### Freight Rail

| Type | kg CO2e/tonne-km |
|------|------------------|
| Diesel freight | 0.024 |
| Electric freight | 0.009 |
| Average freight | 0.016 |

## Aviation

### Domestic Flights

| Class | kg CO2e/passenger-km | kg CO2e/passenger-mile |
|-------|---------------------|------------------------|
| Average | 0.246 | 0.396 |
| Economy | 0.244 | 0.393 |
| Business | 0.366 | 0.589 |

### Short-Haul International (<3,700 km)

| Class | kg CO2e/passenger-km | kg CO2e/passenger-mile |
|-------|---------------------|------------------------|
| Average | 0.153 | 0.246 |
| Economy | 0.148 | 0.238 |
| Premium Economy | 0.237 | 0.381 |
| Business | 0.429 | 0.691 |
| First Class | 0.591 | 0.951 |

### Long-Haul International (>3,700 km)

| Class | kg CO2e/passenger-km | kg CO2e/passenger-mile |
|-------|---------------------|------------------------|
| Average | 0.195 | 0.314 |
| Economy | 0.148 | 0.238 |
| Premium Economy | 0.237 | 0.381 |
| Business | 0.429 | 0.691 |
| First Class | 0.591 | 0.951 |

### Radiative Forcing

For more accurate climate impact, multiply aviation emissions by:
- **With RF factor**: 1.9 (conservative) to 2.7 (with cirrus)
- **Note**: RF captures non-CO2 effects (contrails, NOx, etc.)

### Air Freight

| Type | kg CO2e/tonne-km |
|------|------------------|
| Long-haul freight | 0.602 |
| Short-haul freight | 1.128 |
| International freight (average) | 0.646 |
| Domestic freight | 1.882 |

## Maritime/Shipping

### Passenger Ferries

| Type | kg CO2e/passenger-km |
|------|---------------------|
| Foot passenger | 0.019 |
| Car passenger | 0.129 |
| Average | 0.113 |

### Freight Shipping

| Vessel Type | kg CO2e/tonne-km |
|-------------|------------------|
| Container ship (average) | 0.016 |
| Container ship (large) | 0.008 |
| Bulk carrier | 0.003 |
| General cargo | 0.012 |
| RoRo ferry | 0.032 |
| Tanker (crude) | 0.005 |
| Tanker (products) | 0.009 |

## Bus and Coach

| Type | kg CO2e/passenger-km |
|------|---------------------|
| Local bus (average) | 0.103 |
| Local bus (not London) | 0.120 |
| Local bus (London) | 0.079 |
| Coach | 0.027 |

## Taxi and Private Hire

| Type | kg CO2e/passenger-km | kg CO2e/vehicle-km |
|------|---------------------|-------------------|
| Regular taxi | 0.149 | 0.209 |
| Black cab | 0.220 | 0.308 |

## Well-to-Tank (WTT) Factors

For complete Scope 3 Category 3 reporting, add WTT factors:

### Road Transport WTT

| Vehicle/Fuel | WTT (kg CO2e/km) |
|--------------|------------------|
| Petrol car (avg) | 0.040 |
| Diesel car (avg) | 0.039 |
| HGV diesel | 0.150-0.200 |

### Other Transport WTT

| Mode | WTT Factor |
|------|------------|
| Domestic flight | +25% of direct emissions |
| Short-haul flight | +23% of direct emissions |
| Long-haul flight | +21% of direct emissions |
| Rail | +8% of direct emissions |

## Business Travel Summary

| Mode | Typical Range (kg CO2e/km) |
|------|---------------------------|
| Walking/Cycling | 0 |
| Electric scooter | 0.005-0.015 |
| Rail (average) | 0.030-0.040 |
| Bus/Coach | 0.025-0.120 |
| Electric car | 0.045-0.065 |
| Hybrid car | 0.070-0.120 |
| Petrol/Diesel car | 0.140-0.280 |
| Short-haul flight | 0.150-0.430 |
| Long-haul flight | 0.150-0.590 |

## Data Sources

- UK Government GHG Conversion Factors 2023
- DEFRA/BEIS emission factors
- ICAO Carbon Emissions Calculator methodology
- EPA Emission Factors Hub
- IMO GHG Study

## Calculation Tips

1. **Occupancy matters**: Use per-passenger-km for accurate comparisons
2. **Load factors**: Freight factors assume average load - adjust for actual loads
3. **Return trips**: Don't forget to double one-way calculations
4. **Class of travel**: Business/first class has 2-4x economy emissions
5. **Electric vehicles**: Report electricity consumption in Scope 2
