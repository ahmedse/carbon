# Evidence Files for Alamein Campus

Place real PDF/JPEG/PNG files here to upload as evidence during Phase 3 of the test journey.

## Expected files (create or replace with real documents):

| File | Description | Attach To | Row |
|------|-------------|-----------|-----|
| `alamein-gen-test-report-mar2024.pdf` | Generator test report for Medicine building, March 2024 | M1: `med_gen_log` | GEN-MED-01, 2024-03-15 |
| `alamein-fuel-invoice-jan2024.pdf` | Misr Petroleum fuel invoice, January 2024 | M6: `fleet_fuel_log` | Jan 2024 |
| `alamein-elec-bill-hosp-jan2024.pdf` | Hospital main building electricity bill, January 2024 | M14: `hospital_electricity` | HOSP-MAIN, 2024-01-01 |
| `alamein-procurement-po-mar2024.pdf` | MRI contrast agent purchase order, March 2024 | M5: `med_procurement` | MRI contrast agent, 2024-03-20 |

## How to create placeholder files (if you don't have real ones):

```bash
# Create simple text files renamed as PDF for testing:
echo "ALAMEIN CAMPUS — Generator Test Report — March 2024
College of Medicine
Generator: GEN-MED-01
Test Date: 2024-03-15
Result: PASS
Technician: Eng. Mahmoud Hassan" > alamein-gen-test-report-mar2024.pdf

echo "ALAMEIN CAMPUS — Fuel Invoice — January 2024
Supplier: Misr Petroleum
Date: 2024-01-31
Gasoline: 1,850 L
Diesel: 4,200 L
Total: EGP 78,500" > alamein-fuel-invoice-jan2024.pdf

echo "ALAMEIN CAMPUS — Electricity Bill — January 2024
Building: HOSP-MAIN (Educational Hospital)
Meter: MTR-HOSP-MAIN
Consumption: 125,000 kWh
Cost: EGP 35,750" > alamein-elec-bill-hosp-jan2024.pdf

echo "ALAMEIN CAMPUS — Purchase Order — March 2024
Department: Financial Affairs
Item: MRI Contrast Agent
Supplier: Siemens Health
Quantity: 1 lot
Value: USD 8,200
PO Number: ALM-PO-2024-0391" > alamein-procurement-po-mar2024.pdf
```

## Upload instructions

1. In the frontend, navigate to the Data Entry page for the target table
2. Click the row to open the right panel
3. Switch to the **Evidence** tab
4. Click **Upload** and select the file
5. Verify: the file appears in the Evidence viewer
6. Verify: the Trust tab shows "1 evidence document" for that module
