import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";
import { fetchModules } from "../api/modules";
import { apiFetch, refreshAccessToken } from "../api/api"; // <-- Add this import

// --- Helpers for token management ---
// refreshAccessToken is imported from api.js (single source of truth)
// to prevent duplicate refresh race conditions between AuthContext timer
// and api.js 401 retry handler. Both share one refreshInFlight lock.

// --- Auth Context ---
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tablesByModule, setTablesByModule] = useState({});
  const [availablePerspectives, setAvailablePerspectives] = useState([]);
  const [isGlobalAdminFlag, setIsGlobalAdminFlag] = useState(false);
  const [userCapabilities, setUserCapabilities] = useState(null);
  const [currentPerspective, setCurrentPerspective] = useState(() => {
    return localStorage.getItem("carbon_perspective") || "dashboards";
  });

  // Perspective setter that persists to localStorage
  const setPerspectiveActive = (perspective) => {
    setCurrentPerspective(perspective);
    localStorage.setItem("carbon_perspective", perspective);
  };

  // --- Timers and refs ---
  const inactivityTimeout = 60 * 60 * 1000; // 1 hour
  const refreshIntervalMs = 10 * 60 * 1000; // 10 minutes
  const inactivityTimerRef = useRef();
  const refreshTimerRef = useRef();
  const loginInFlightRef = useRef(false);

  // Debug helper (disabled by default, enable for debugging)
  const debug = (..._args) => { /* if (import.meta.env.DEV) console.log("[Auth]", ..._args); */ };

  // --- Fetch perspective context from backend ---
  const fetchPerspectiveContext = async (token) => {
    try {
      const data = await apiFetch('accounts/me/context/', { method: 'GET', token }); // fetch perspective
      // Phase 12 enabler — expose the numeric owner id so shared-thread
      // ownership checks can compare conversation.user_id against user.id.
      if (data?.user?.id != null) {
        localStorage.setItem("user_id", String(data.user.id));
        setUser((prev) => (prev ? { ...prev, id: data.user.id } : prev));
      }
      setAvailablePerspectives(data.perspectives || []);
      setIsGlobalAdminFlag(data.is_global_admin === true);
      // Store capabilities for CBAC (capability-based access control)
      const caps = data.capabilities || [];
      setUserCapabilities(caps);
      localStorage.setItem("user_capabilities", JSON.stringify(caps));
      // Store the authoritative flag for offline/reload recovery
      localStorage.setItem("is_global_admin", data.is_global_admin === true ? "1" : "0");
      // Set default perspective based on available ones
      const defaultPerspective = data.perspectives?.[0] || 'dashboards';
      if (!localStorage.getItem("carbon_perspective")) {
        setCurrentPerspective(defaultPerspective);
        localStorage.setItem("carbon_perspective", defaultPerspective);
      }
      localStorage.setItem(
        "available_perspectives",
        JSON.stringify(data.perspectives || [])
      );
      // Store org_units from backend for data owner checks
      if (data.org_units) {
        localStorage.setItem("org_units", JSON.stringify(data.org_units));
      }
      return data;
    } catch (err) {
      console.error("Failed to fetch perspective context:", err);
      return null;
    }
  };

  // --- Local Storage Sync on mount ---
  useEffect(() => {
    try {
      const storedUser = JSON.parse(localStorage.getItem("user"));
      const storedProjects = JSON.parse(localStorage.getItem("projects"));
      const storedContext = JSON.parse(localStorage.getItem("context"));
      const storedPerspectives = JSON.parse(
        localStorage.getItem("available_perspectives") || "[]"
      );
      if (storedUser?.token) {
        setUser({ ...storedUser, id: localStorage.getItem("user_id") || storedUser.id || undefined });
      }
      if (Array.isArray(storedProjects)) setProjects(storedProjects);
      if (storedContext) setContext(storedContext);
      const storedIsGlobalAdmin = localStorage.getItem("is_global_admin") === "1";
      setIsGlobalAdminFlag(storedIsGlobalAdmin);
      // Restore capabilities from localStorage
      try {
        const storedCaps = JSON.parse(localStorage.getItem("user_capabilities"));
        if (Array.isArray(storedCaps)) setUserCapabilities(storedCaps);
      } catch { /* ignore */ }
      if (Array.isArray(storedPerspectives) && storedPerspectives.length) {
        setAvailablePerspectives(storedPerspectives);
      }
    } catch { /* ignore parse errors */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (user) {
      fetchPerspectiveContext(user.token).catch(() => {
        console.warn("Failed to refresh perspective context on reload");
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.token]);

  // --- Inactivity & periodic token refresh logic ---
  useEffect(() => {
    if (!user) return;

    // --- Reset inactivity timer and periodic refresh ---
    const resetTimers = () => {
      // Inactivity logout timer
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = setTimeout(() => {
        debug("Logging out due to inactivity");
        logout("inactivity");
      }, inactivityTimeout);

      // Background token refresh
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = setInterval(async () => {
        try {
          debug("Background access token refresh...");
          await refreshAccessToken();
        } catch (err) {
          debug("Token refresh failed:", err);
          logout("refreshError");
        }
      }, refreshIntervalMs);
    };

    // --- Listen for user activity ---
    ["mousemove", "keydown", "mousedown", "touchstart"].forEach(e =>
      window.addEventListener(e, resetTimers)
    );
    resetTimers();

    // --- Proactive refresh when user returns to the tab ---
    // Browser throttles setInterval for background tabs to 1/min,
    // so a 10-min refresh timer can miss the 15-min (now 60-min) expiry window.
    // On visibility change → visible, immediately refresh the access token.
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        debug('Tab re-focused — proactive token refresh');
        refreshAccessToken().catch(() => {
          // Silently fail — the next API call will trigger a proper refresh or logout
          debug('Proactive refresh on tab focus failed');
        });
        resetTimers();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // --- Cleanup on unmount/logout ---
    return () => {
      ["mousemove", "keydown", "mousedown", "touchstart"].forEach(e =>
        window.removeEventListener(e, resetTimers)
      );
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
    // eslint-disable-next-line
  }, [user]);

  // --- Ensure a working context exists whenever the user is present ---
  useEffect(() => {
    if (user && !context) {
      buildContext(user);
    }
    // eslint-disable-next-line
  }, [user, context]);

  // --- Refetch tables when context changes ---
  useEffect(() => {
    if (user && context?.modules) {
      refetchTables();
    }
    // eslint-disable-next-line
  }, [user, context?.modules]);

  // --- Login: fetch tokens, user roles, and build project list ---
  const login = async ({ username, password }) => {
    // Prevent duplicate concurrent login attempts
    if (loginInFlightRef.current) {
      debug("Login already in progress - ignoring duplicate request");
      return { requireProjectSelection: true };
    }
    loginInFlightRef.current = true;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}${API_ROUTES.token}`, { // login token endpoint
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      const { access, refresh } = await res.json();

      // Fetch roles
      const rolesData = await apiFetch('accounts/my-roles/', { method: 'GET', token: access }); // fetch roles
      const { roles } = rolesData;

      // Fetch perspective context
      const perspective = await fetchPerspectiveContext(access);

      const userObj = { id: perspective?.user?.id, username, token: access, refresh, roles };
      setUser(userObj);
      localStorage.setItem("user", JSON.stringify(userObj));
      localStorage.setItem("access", access);
      localStorage.setItem("refresh", refresh);

      // I18N-5: sync any pre-login language choice (localStorage `carbon.lang`)
      // up to the account so the post-login reconciliation effect doesn't
      // revert the user to the server default on the next full reload. Only
      // runs when the user has an explicit local choice — fresh devices leave
      // localStorage unset and let the server preference win (cross-device).
      try {
        const uiLang = localStorage.getItem('carbon.lang');
        if (uiLang === 'ar' || uiLang === 'en') {
          await apiFetch('accounts/me/preferences/', {
            method: 'PATCH',
            token: access,
            body: { language: uiLang },
          });
        }
      } catch {
        // Best-effort — reconciliation will fall back to localStorage.
      }

      // Build context + get landing path for smart redirect.
      const ctx = await buildContext(userObj);

      debug("Login success", userObj);
      loginInFlightRef.current = false;
      setLoading(false);
      return { requireProjectSelection: false, landingPath: ctx?.landingPath || '/dashboard' };
    } catch (err) {
      setLoading(false);
      loginInFlightRef.current = false;
      throw err;
    }
  };

  // --- Build the working context (the modules the user can access). No project concept. ---
  const buildContext = async (_user = user) => {
    setLoading(true);
    try {
      const u = _user || user;
      let modules = [];
      try {
        const res = await fetchModules(u.token);
        modules = Array.isArray(res) ? res : (res?.results || []);
      } catch (e) {
        modules = [];
        if (import.meta.env.DEV) console.error("[Auth] Failed to fetch modules", e);
      }

      // Determine landing path: data-owners with no admin role go straight to their first module.
      const isAdmin = (u.roles || []).some(r => r.active !== false && r.role === 'admins_group');
      const isDataOwner = (u.roles || []).some(r => r.active !== false && r.role === 'dataowners_group');
      let landingPath = '/dashboard';
      if (!isAdmin && isDataOwner && modules.length > 0) {
        landingPath = `/modules/${modules[0].id}`;
      }

      const ctx = {
        projectId: "carbon",
        project: { id: "carbon", name: "Carbon" },
        projectRoles: u.roles || [],
        modules,
        landingPath,
        org_units: JSON.parse(localStorage.getItem("org_units") || "[]"),
      };
      setContext(ctx);
      setProjects([ctx.project]);
      localStorage.setItem("context", JSON.stringify(ctx));
      setLoading(false);
      return ctx;
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  // Backward-compatible alias — older components still call selectProject().
  const selectProject = async (_projectId, _user = user) => buildContext(_user);


  // --- Logout: clear all state, timers, and storage ---
  const logout = async (reason) => {
    debug("Logout called:", reason);

    // Best-effort backend logout (blacklist refresh token). Always continue local logout.
    try {
      const refresh = localStorage.getItem("refresh");
      const access = localStorage.getItem("access");
      if (refresh && access && API_ROUTES.logout) {
        await fetch(`${API_BASE_URL}${API_ROUTES.logout}`, { // backend logout (best-effort)
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${access}`,
          },
          body: JSON.stringify({ refresh }),
        });
      }
    } catch {
      // Ignore network/token errors during logout.
    }

    setUser(null);
    setProjects([]);
    setContext(null);
    setTablesByModule({});
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    localStorage.clear();
    window.location.href = `${import.meta.env.VITE_BASE}login?expired=1`;
  };

  // --- Fetch tables by module (fixed to use apiFetch with auto token refresh) ---
  const refetchTables = async () => {
    if (!user || !context?.projectId || !context?.modules) return;
    try {
      const grouped = {};
      // Limit concurrency to avoid browser connection pool exhaustion
      const CONCURRENCY = 5;
      for (let i = 0; i < context.modules.length; i += CONCURRENCY) {
        const batch = context.modules.slice(i, i + CONCURRENCY);
        await Promise.all(
          batch.map(async (mod) => {
            try {
              // Use apiFetch for auto JWT refresh
              const data = await apiFetch(API_ROUTES.tables, {
                project_id: context.projectId,
                module_id: mod.id,
                token: user.token, // optional, apiFetch can also use localStorage
              });
              // API returns paginated { results: [...] } — extract array
              grouped[String(mod.id)] = Array.isArray(data) ? data : (data?.results || []);
            } catch (err) {
              // Optionally, handle unauthorized (if still fails), or set as empty
              grouped[String(mod.id)] = [];
              if (import.meta.env.DEV) console.error("Failed to fetch tables for module", mod.id, err);
            }
          })
        );
      }
      setTablesByModule(grouped);
    } catch (err) {
      setTablesByModule({});
      if (import.meta.env.DEV) console.error("Failed to fetch tables", err);
    }
  };

  // --- Role helpers ---
  const hasRole = (roleName) =>
    (user?.roles || []).some(r => r?.active && r.role === roleName) ||
    context?.projectRoles?.some(r => r.role === roleName);

  const canSchemaAdmin = () =>
    (user?.roles || []).some(r => r?.active && (r.role === "admins_group" || r.role === "admin")) ||
    context?.projectRoles?.some(r => r.role === "admins_group" || r.role === "admin");

  const canManageAllModules = () =>
    (user?.roles || []).some(r => r?.active && ["admins_group", "admin", "auditors_group", "auditor"].includes(r.role)) ||
    context?.projectRoles?.some(r => ["admins_group", "admin", "auditors_group", "auditor"].includes(r.role));

  const canManageAssignedModules = () =>
    (user?.roles || []).some(r => r?.active && (r.role === "dataowners_group" || r.role === "dataowner")) ||
    context?.projectRoles?.some(r => r.role === "dataowners_group" || r.role === "dataowner");

  return (
    <AuthContext.Provider
      value={{
        user,
        token: user?.token,
        projects,
        context,
        loading,
        login,
        selectProject,
        logout,
        hasRole,
        canSchemaAdmin,
        canManageAllModules,
        canManageAssignedModules,
        tablesByModule,
        refetchTables,
        currentPerspective,
        setPerspective: setPerspectiveActive,
        availablePerspectives,
        isGlobalAdminFlag,
        userCapabilities,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext) || {
  user: null,
  token: null,
  projects: [],
  context: null,
  loading: false,
  login: async () => ({ requireProjectSelection: false }),
  selectProject: async () => true,
  logout: async () => {},
  hasRole: () => false,
  canSchemaAdmin: () => false,
  canManageAllModules: () => false,
  canManageAssignedModules: () => false,
  tablesByModule: {},
  refetchTables: async () => {},
  currentPerspective: 'dashboards',
  setPerspective: () => {},
  availablePerspectives: [],
  isGlobalAdminFlag: false,
};