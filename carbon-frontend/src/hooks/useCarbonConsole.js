// src/hooks/useCarbonConsole.js
// Wraps fetchConsoleData — console stats, active period, alerts, recent activity.
// Matches CarbonConsolePage.jsx call shape: fetchConsoleData(token).
// Returns { data, loading, error, refetch } — data only.

import { fetchConsoleData } from "../api/emissions";
import { useApi } from "./useApi";

export function useCarbonConsole() {
  return useApi(fetchConsoleData, []);
}
