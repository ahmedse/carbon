// src/hooks/useOwnerDashboard.js
// Wraps owner dashboard API calls (fetchOwnerDashboard + fetchOwnerSummary)
// with org-unit / period selection state, matching DataOwnerDashboardPage.jsx.
// Returns { data, loading, error, orgUnitId, setOrgUnitId, periodId, setPeriodId, refetch }.

import { useCallback, useState } from "react";
import { fetchOwnerDashboard, fetchOwnerSummary } from "../api/emissions";
import { useApi } from "./useApi";

export function useOwnerDashboard() {
  const [orgUnitId, setOrgUnitId] = useState(null);
  const [periodId, setPeriodId] = useState(null);

  const fetchFn = useCallback(
    (token) =>
      Promise.all([
        fetchOwnerDashboard(token, orgUnitId, periodId),
        fetchOwnerSummary(token),
      ]).then(([dashRes, summaryRes]) => ({
        ...dashRes,
        summary: summaryRes?.summary || null,
        org_unit: dashRes?.org_unit || summaryRes?.org_unit || null,
      })),
    [orgUnitId, periodId]
  );

  const { data, loading, error, refetch } = useApi(fetchFn, [
    orgUnitId,
    periodId,
  ]);

  return {
    data,
    loading,
    error,
    orgUnitId,
    setOrgUnitId,
    periodId,
    setPeriodId,
    refetch,
  };
}
