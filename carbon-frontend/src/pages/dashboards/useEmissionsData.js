// File: src/pages/dashboards/useEmissionsData.js
// Custom hook for fetching REAL emissions dashboard data from the backend API

import { useState, useEffect, useCallback } from "react";
import { fetchEmissionsDashboard, fetchYearlyComparison } from "../../api/emissions";
import { useAuth } from "../../auth/AuthContext";

/**
 * Hook to fetch real emissions data from /emissions/dashboard/ API
 * 
 * The backend returns:
 * - total_co2e_tonnes: Total emissions in tonnes
 * - scope_breakdown: Array of { scope, scope_name, co2e_tonnes, percentage }
 * - category_breakdown: Array of { category, category_name, scope, co2e_tonnes, count }
 * - monthly_trend: Array of { month, month_name, scope1, scope2, scope3, total }
 * - data_quality_score: Integer 0-100
 * - calculation_count: Number of calculation records
 * - last_updated: Timestamp
 */
export function useEmissionsData(year = new Date().getFullYear()) {
  const { user, context } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!user?.token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchEmissionsDashboard(
        {
          project_id: context?.projectId,
          year: year,
        },
        user.token
      );

      // Transform API response into dashboard-friendly format
      const transformed = transformApiResponse(result);
      setData(transformed);
    } catch (err) {
      console.error("Failed to fetch emissions data:", err);
      setError(err.message || "Failed to load emissions data");
    } finally {
      setLoading(false);
    }
  }, [user?.token, context?.projectId, year]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

/**
 * Transform the raw API response into a format optimized for dashboard components
 */
function transformApiResponse(apiData) {
  if (!apiData) return null;

  // Extract scope data from scope_breakdown array
  const scopeMap = {};
  (apiData.scope_breakdown || []).forEach((s) => {
    scopeMap[`scope${s.scope}`] = {
      tonnes: s.co2e_tonnes || 0,
      percentage: s.percentage || 0,
      name: s.scope_name || `Scope ${s.scope}`,
    };
  });

  // Build emissions summary
  const emissions = {
    total: apiData.total_co2e_tonnes || 0,
    scope1: scopeMap.scope1?.tonnes || 0,
    scope2: scopeMap.scope2?.tonnes || 0,
    scope3: scopeMap.scope3?.tonnes || 0,
  };

  // Build category breakdown for charts
  const categoryBreakdown = (apiData.category_breakdown || []).map((cat) => ({
    name: cat.category_name || cat.category,
    category: cat.category,
    scope: cat.scope,
    value: cat.co2e_tonnes || 0,
    count: cat.count || 0,
    percentage: emissions.total > 0 
      ? Math.round((cat.co2e_tonnes / emissions.total) * 100 * 10) / 10 
      : 0,
  }));

  // Sort categories by value descending
  categoryBreakdown.sort((a, b) => b.value - a.value);

  // Build monthly trend data
  const monthlyTrend = (apiData.monthly_trend || []).map((m) => ({
    month: m.month_name || m.month,
    monthNumber: parseInt(m.month) || 0,
    scope1: m.scope1 || 0,
    scope2: m.scope2 || 0,
    scope3: m.scope3 || 0,
    total: m.total || 0,
  }));

  // Calculate which months have data for data quality
  const monthsWithData = monthlyTrend.filter((m) => m.total > 0).length;

  // Get top emission sources from category breakdown
  const topSources = categoryBreakdown.slice(0, 5).map((cat, idx) => ({
    name: cat.name,
    value: cat.value,
    percentage: cat.percentage,
    scope: cat.scope,
    rank: idx + 1,
  }));

  // Derive insights from the data
  const insights = generateInsights(emissions, categoryBreakdown, monthlyTrend);

  return {
    // Summary metrics
    emissions,
    totalEmissions: emissions.total,
    
    // Scope breakdown for pie/donut charts
    scopeBreakdown: {
      labels: ["Scope 1", "Scope 2", "Scope 3"],
      data: [emissions.scope1, emissions.scope2, emissions.scope3],
      percentages: [
        scopeMap.scope1?.percentage || 0,
        scopeMap.scope2?.percentage || 0,
        scopeMap.scope3?.percentage || 0,
      ],
    },
    
    // Category data for bar charts
    categoryBreakdown,
    topSources,
    
    // Monthly trend for line charts
    monthlyTrend,
    monthlyData: monthlyTrend.map((m) => m.total),
    monthLabels: monthlyTrend.map((m) => m.month),
    
    // Data quality metrics
    dataQuality: {
      score: apiData.data_quality_score || 0,
      calculationCount: apiData.calculation_count || 0,
      monthsWithData,
      completeness: Math.round((monthsWithData / 12) * 100),
    },
    
    // Metadata
    lastUpdated: apiData.last_updated 
      ? new Date(apiData.last_updated).toLocaleDateString() 
      : new Date().toLocaleDateString(),
    reportingPeriod: apiData.reporting_period,
    
    // Auto-generated insights
    insights,
    
    // Raw data for debugging
    _raw: apiData,
  };
}

/**
 * Generate insights based on actual data patterns
 */
function generateInsights(emissions, categories, monthlyTrend) {
  const insights = [];

  // Find dominant scope
  const scopes = [
    { name: "Scope 1", value: emissions.scope1 },
    { name: "Scope 2", value: emissions.scope2 },
    { name: "Scope 3", value: emissions.scope3 },
  ].sort((a, b) => b.value - a.value);

  if (scopes[0].value > 0) {
    const pct = emissions.total > 0 
      ? Math.round((scopes[0].value / emissions.total) * 100) 
      : 0;
    insights.push({
      type: "info",
      text: `${scopes[0].name} represents ${pct}% of total emissions (${scopes[0].value.toLocaleString()} tonnes)`,
    });
  }

  // Find top category
  if (categories.length > 0) {
    const top = categories[0];
    insights.push({
      type: top.scope === 2 ? "warning" : "info",
      text: `${top.name} is your largest emission source at ${top.value.toLocaleString()} tonnes (${top.percentage}%)`,
    });
  }

  // Analyze monthly trend
  const nonZeroMonths = monthlyTrend.filter((m) => m.total > 0);
  if (nonZeroMonths.length >= 2) {
    const firstHalf = nonZeroMonths.slice(0, Math.ceil(nonZeroMonths.length / 2));
    const secondHalf = nonZeroMonths.slice(Math.ceil(nonZeroMonths.length / 2));
    
    const firstAvg = firstHalf.reduce((s, m) => s + m.total, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((s, m) => s + m.total, 0) / secondHalf.length;
    
    if (secondAvg < firstAvg * 0.9) {
      const reduction = Math.round((1 - secondAvg / firstAvg) * 100);
      insights.push({
        type: "positive",
        text: `Emissions trending down ${reduction}% in recent months`,
      });
    } else if (secondAvg > firstAvg * 1.1) {
      const increase = Math.round((secondAvg / firstAvg - 1) * 100);
      insights.push({
        type: "warning",
        text: `Emissions trending up ${increase}% in recent months - review needed`,
      });
    }
  }

  // Data completeness insight
  const dataMonths = nonZeroMonths.length;
  if (dataMonths === 12) {
    insights.push({
      type: "positive",
      text: "Data collection is complete for all 12 months",
    });
  } else if (dataMonths > 0 && dataMonths < 12) {
    insights.push({
      type: "warning",
      text: `Data available for ${dataMonths} of 12 months - ${12 - dataMonths} months missing`,
    });
  }

  return insights.slice(0, 4); // Limit to 4 insights
}

/**
 * Hook to compare emissions between two periods
 */
export function useEmissionsComparison(currentYear, previousYear) {
  const { user, context } = useAuth();
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!user?.token) {
      setLoading(false);
      return;
    }

    const fetchComparison = async () => {
      setLoading(true);
      try {
        const [current, previous] = await Promise.all([
          fetchEmissionsDashboard({ project_id: context?.projectId, year: currentYear }, user.token),
          fetchEmissionsDashboard({ project_id: context?.projectId, year: previousYear }, user.token),
        ]);

        const currentTotal = current.total_co2e_tonnes || 0;
        const previousTotal = previous.total_co2e_tonnes || 0;
        
        const changePercent = previousTotal > 0
          ? Math.round(((currentTotal - previousTotal) / previousTotal) * 100 * 10) / 10
          : 0;

        setComparison({
          currentYear,
          previousYear,
          currentTotal,
          previousTotal,
          changePercent,
          changeAbsolute: currentTotal - previousTotal,
          isReduction: changePercent < 0,
        });
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchComparison();
  }, [user?.token, context?.projectId, currentYear, previousYear]);

  return { comparison, loading, error };
}

/**
 * Hook to fetch yearly comparison data for targets dashboard
 * Uses the /emissions/yearly-comparison/ endpoint
 * 
 * Returns:
 * - baselineYear: The year marked as baseline
 * - baselineTotal: Total emissions in baseline year (tonnes)
 * - currentYear: Most recent year with data
 * - yearlyData: Array of year-by-year emissions data
 * - targets: Array of target values by year
 * - reductionFromBaseline: Current reduction percentage from baseline
 */
export function useYearlyComparison(years = "2020,2021,2022,2023,2024,2025") {
  const { user, context } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!user?.token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchYearlyComparison(
        { project_id: context?.projectId, years },
        user.token
      );

      // Transform data for dashboard use
      const yearlyData = (result.yearly_comparison || []).map((y) => ({
        year: y.year,
        total: y.total_co2e_tonnes || 0,
        scope1: y.scope1 || 0,
        scope2: y.scope2 || 0,
        scope3: y.scope3 || 0,
        reductionFromBaseline: y.reduction_from_baseline || 0,
        yoyChange: y.yoy_change || 0,
        isBaseline: y.is_baseline || false,
        calculationCount: y.calculation_count || 0,
      }));

      const targets = (result.targets || []).map((t) => ({
        year: t.year,
        targetTotal: t.target_co2e_tonnes || 0,
        targetReductionPct: t.target_reduction_pct || 0,
      }));

      // Find current year data
      const currentYearData = yearlyData[yearlyData.length - 1] || {};
      
      setData({
        baselineYear: result.baseline_year,
        baselineTotal: result.baseline_total_tonnes || 0,
        currentYear: result.current_year,
        currentTotal: currentYearData.total || 0,
        reductionFromBaseline: currentYearData.reductionFromBaseline || 0,
        yearlyData,
        targets,
        // Calculate target for 2030 (50% reduction from baseline)
        target2030: (result.baseline_total_tonnes || 0) * 0.5,
      });
    } catch (err) {
      console.error("Failed to fetch yearly comparison:", err);
      setError(err.message || "Failed to load yearly comparison data");
    } finally {
      setLoading(false);
    }
  }, [user?.token, context?.projectId, years]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
