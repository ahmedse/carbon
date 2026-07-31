// src/hooks/useMyData.js
// Wraps my-data API calls (fetchMyData + fetchOwnerActivity) with client-side
// filter state (search / scope / status — applied by the consuming page,
// per MyDataPage.jsx).
// Returns { data, loading, error, filters, setFilters, refetch } — data only.

import { useCallback, useState } from "react";
import { fetchMyData, fetchOwnerActivity } from "../api/emissions";
import { useApi } from "./useApi";

export function useMyData() {
  // Client-side filters, matching MyDataPage.jsx (searchText / scope / status).
  const [filters, setFilters] = useState({
    search: "",
    scope: "all",
    status: "all",
  });

  const fetchFn = useCallback((token) => {
    return Promise.all([
      fetchMyData(token),
      fetchOwnerActivity({ limit: 15 }, token).catch(() => []),
    ]).then(([myData, activity]) => ({
      ...myData,
      activity: Array.isArray(activity) ? activity : [],
    }));
  }, []);

  const { data, loading, error, refetch } = useApi(fetchFn, []);

  return { data, loading, error, filters, setFilters, refetch };
}
