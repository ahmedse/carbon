// File: src/components/dashboard/useDashboardData.js
// Custom hook for fetching real dashboard data from API

import { useState, useEffect } from "react";
import { apiFetch } from "../../api/api";
import { API_ROUTES } from "../../config";

export function useDashboardData(projectId, token) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId || !token) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch all data rows from all modules using API_ROUTES (no hardcoded paths)
        const modules = await apiFetch(API_ROUTES.modules, {
          token,
          project_id: projectId,
        });

        const allRows = [];
        
        // Fetch rows from each module
        for (const module of modules || []) {
          try {
            const tables = await apiFetch(API_ROUTES.tables, {
              token,
              project_id: projectId,
              module_id: module.id,
            });

            for (const table of tables || []) {
              try {
                const rows = await apiFetch(API_ROUTES.rows, {
                  token,
                  project_id: projectId,
                  module_id: module.id,
                  table_id: table.id,
                });
                
                allRows.push({
                  moduleId: module.id,
                  moduleName: module.name,
                  scope: module.scope,
                  tableId: table.id,
                  tableName: table.name,
                  rows: rows || [],
                });
              } catch (err) {
                console.warn(`Failed to fetch rows for table ${table.id}:`, err);
              }
            }
          } catch (err) {
            console.warn(`Failed to fetch tables for module ${module.id}:`, err);
          }
        }

        // Process and aggregate data
        const processedData = processRawData(allRows);
        setData(processedData);
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
        setError(err.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId, token]);

  return { data, loading, error };
}

function processRawData(allRows) {
  // Initialize aggregates
  const summary = {
    emissions: { scope1: 0, scope2: 0, scope3: 0, total: 0 },
    energy: { total: 0 },
    water: { total: 0 },
    dataCompleteness: 0,
    lastUpdate: new Date().toISOString().split('T')[0],
  };

  const monthlyEmissions = {};
  const scopeBreakdown = { scope1: 0, scope2: 0, scope3: 0 };
  const energyByMonth = {};
  const waterByMonth = {};

  // Process each data source
  allRows.forEach(({ scope, rows, moduleName }) => {
    rows.forEach(row => {
      const values = row.values || {};
      const year = values.reporting_year;
      const month = values.reporting_month;
      const monthKey = `${year}-${getMonthNumber(month)}`;

      // Aggregate CO2e emissions
      const co2e = parseFloat(values.co2e_emissions || 0);
      if (co2e > 0) {
        if (scope === 1) {
          scopeBreakdown.scope1 += co2e;
        } else if (scope === 2) {
          scopeBreakdown.scope2 += co2e;
        } else if (scope === 3) {
          scopeBreakdown.scope3 += co2e;
        }

        // Monthly aggregation
        if (monthKey && monthKey !== 'undefined-undefined') {
          monthlyEmissions[monthKey] = (monthlyEmissions[monthKey] || 0) + co2e;
        }
      }

      // Aggregate energy
      const energy = parseFloat(values.consumption_kwh || 0);
      if (energy > 0) {
        summary.energy.total += energy;
        if (monthKey && monthKey !== 'undefined-undefined') {
          energyByMonth[monthKey] = (energyByMonth[monthKey] || 0) + energy;
        }
      }

      // Aggregate water
      const water = parseFloat(values.consumption_m3 || 0);
      if (water > 0) {
        summary.water.total += water;
        if (monthKey && monthKey !== 'undefined-undefined') {
          waterByMonth[monthKey] = (waterByMonth[monthKey] || 0) + water;
        }
      }
    });
  });

  // Convert kg to tonnes for display
  summary.emissions.scope1 = Math.round(scopeBreakdown.scope1 / 1000);
  summary.emissions.scope2 = Math.round(scopeBreakdown.scope2 / 1000);
  summary.emissions.scope3 = Math.round(scopeBreakdown.scope3 / 1000);
  summary.emissions.total = summary.emissions.scope1 + summary.emissions.scope2 + summary.emissions.scope3;

  // Calculate data completeness (simplified)
  const totalExpectedRows = allRows.reduce((sum, item) => sum + (item.rows?.length || 0), 0);
  summary.dataCompleteness = totalExpectedRows > 0 ? Math.min(100, Math.round((totalExpectedRows / 500) * 100)) : 0;

  // Sort monthly data
  const sortedMonths = Object.keys(monthlyEmissions).sort();
  const last12Months = sortedMonths.slice(-12);

  return {
    summary,
    monthlyEmissions: last12Months.map(key => ({
      month: formatMonthKey(key),
      emissions: Math.round(monthlyEmissions[key] / 1000), // Convert to tonnes
      energy: Math.round(energyByMonth[key] || 0),
      water: Math.round(waterByMonth[key] || 0),
    })),
    scopeBreakdown: {
      labels: ["Scope 1", "Scope 2", "Scope 3"],
      data: [summary.emissions.scope1, summary.emissions.scope2, summary.emissions.scope3],
    },
    rawData: allRows,
  };
}

function getMonthNumber(monthName) {
  const months = {
    January: "01", February: "02", March: "03", April: "04",
    May: "05", June: "06", July: "07", August: "08",
    September: "09", October: "10", November: "11", December: "12",
  };
  return months[monthName] || "00";
}

function formatMonthKey(key) {
  const [year, month] = key.split('-');
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return monthNames[parseInt(month) - 1] || month;
}
