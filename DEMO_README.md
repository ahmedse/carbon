# Carbon Emissions Calculator - Demo Guide

## 🎯 Executive Summary

This demo showcases the Carbon Emissions Management System, a comprehensive platform for tracking, calculating, and reporting greenhouse gas (GHG) emissions across all three GHG Protocol scopes.

---

## 🚀 Quick Start

### Access the Demo

1. **Frontend Dashboard**: http://localhost:5173/emissions/dashboard
2. **Emissions Report**: http://localhost:5173/emissions/report
3. **Backend API**: http://localhost:8000/api/v1/emissions/

### Demo Credentials
- **Email**: demo_admin@acme.com
- **Password**: demo123!

---

## 📊 Demo Data Summary

### Company Profile
- **Organization**: Acme Corporation
- **Reporting Year**: FY 2025 (January - December 2025)

### Emissions Overview

| Scope | Description | Emissions (tonnes CO2e) | % of Total |
|-------|-------------|------------------------|------------|
| Scope 1 | Direct Emissions | 625.62 | 24.86% |
| Scope 2 | Indirect Energy | 1,885.17 | 74.92% |
| Scope 3 | Value Chain | 5.30 | 0.21% |
| **TOTAL** | | **2,516.09** | **100%** |

### Data Sources

#### Scope 1 - Direct Emissions
- **Natural Gas Consumption**: 48 monthly records across 4 facilities
  - Office buildings heating
  - Manufacturing facility heating
- **Fleet Vehicles**: 120 records (10 vehicles × 12 months)
  - Mix of petrol and diesel vehicles
  - Sales, delivery, and executive fleet

#### Scope 2 - Indirect Energy
- **Electricity Consumption**: 48 monthly records across 4 facilities
  - Headquarters (Chicago)
  - Manufacturing Plant (Detroit)
  - Data Center (Denver)
  - Regional Office (Atlanta)

#### Scope 3 - Value Chain
- **Business Travel**: 13 trips
  - Domestic and international flights
  - Rail and rental car travel
- **Employee Commuting**: 348 records (data entered, calculations pending)

---

## 🎨 Key Features Demonstrated

### 1. Beautiful Dashboard Visualizations
- **Scope Breakdown Chart**: Doughnut chart showing emission distribution
- **Monthly Trend Line**: Line chart with all three scopes over 12 months
- **Category Breakdown**: Bar chart with detailed emission sources
- **Key Metrics Cards**: Total emissions, calculation count, data quality score

### 2. GHG Protocol Compliance
- Follows GHG Protocol Corporate Standard
- Separate tracking for Scope 1, 2, and 3
- Proper emission factor attribution (EPA, DEFRA sources)

### 3. Automated Calculations
- **229 automated calculations** from raw activity data
- Emission factors from authoritative sources:
  - EPA eGRID (electricity)
  - EPA GHG Inventory (fuels)
  - DEFRA (transport, flights)
- Automatic unit conversions and CO2e calculations

### 4. Multi-tenant Architecture
- Tenant isolation for multiple organizations
- Project-based reporting periods
- Module-based data organization by scope

### 5. Professional Reports
- Executive summary view
- Scope-by-scope breakdown
- Category details with methodology
- Print-ready format

---

## 📱 API Endpoints

### Dashboard Data
```
GET /api/v1/emissions/dashboard/?year=2025
```
Returns scope breakdown, category breakdown, and monthly trends.

### Report Generation
```
GET /api/v1/emissions/report/?year=2025
```
Returns detailed GHG Protocol-compliant report data.

### Emission Factors
```
GET /api/v1/emissions/factors/
```
Lists all available emission factors (165 factors seeded).

### Calculations
```
GET /api/v1/emissions/calculations/
```
Lists all calculated emissions.

---

## 🔧 Technical Architecture

### Backend Stack
- **Framework**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL with multi-tenant support
- **Auth**: JWT-based authentication

### Frontend Stack
- **Framework**: React 19 with Vite
- **UI Library**: Material UI 7
- **Charts**: Chart.js 4 with react-chartjs-2

### Data Model
```
Tenant → Project → Module → DataTable → DataRow
                      ↓
              CalculationRule → Calculation
                      ↓
              EmissionFactor + GWP
```

---

## 🎯 Business Value Highlights

1. **Compliance Ready**: Meets GHG Protocol Corporate Standard requirements
2. **Audit Trail**: Full traceability from source data to emissions
3. **Scalable**: Supports unlimited emission sources and data points
4. **Flexible**: Dynamic schema allows any data structure
5. **Accurate**: Uses authoritative emission factors with automatic updates
6. **Real-time**: Dashboard updates as data is entered
7. **Professional**: Print-ready reports for stakeholder disclosure

---

## 📞 Next Steps for Production

1. Enable authentication for all API endpoints
2. Implement role-based access control
3. Add data import (CSV, Excel)
4. Add comparative analytics (YoY)
5. Add target setting and tracking
6. Implement PDF export for reports

---

*Generated: February 2026*
*Version: 1.0*
