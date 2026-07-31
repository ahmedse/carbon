// src/hooks/useEmissionsDashboard.js
// Wraps fetchEmissionsDashboard with filter state.
// Filters: year, reporting_period_id, org_unit_id (AnalyticsDashboard.jsx pipeline).
// Returns { data, loading, error, filters, setFilters, refetch } — data only.

import { useCallback, useState } from "react";
import { fetchEmissionsDashboard } from "../api/emissions";
import { useApi } from "./useApi";

export function useEmissionsDashboard(initialFilters = {}) {
  const [filters, setFilters] = useState({
    year: initialFilters.year ?? "",
    reporting_period_id: initialFilters.reporting_period_id ?? "",
    org_unit_id: initialFilters.org_unit_id ?? "",
  });

  const fetchFn = useCallback(
    (token) =>
      fetchEmissionsDashboard(
        {
          // org_unit_id is the org-scoping filter; the API fn accepts project_id.
          project_id: filters.org_unit_id || undefined,
          reporting_period_id: filters.reporting_period_id || undefined,
          year: filters.year || undefined,
        },
        token
      ),
    [filters.year, filters.reporting_period_id, filters.org_unit_id]
  );

  const { data, loading, error, refetch } = useApi(fetchFn, [
    filters.year,
    filters.reporting_period_id,
    filters.org_unit_id,
  ]);

  return { data, loading, error, filters, setFilters, refetch };
}
