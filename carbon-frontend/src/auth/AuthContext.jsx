import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";
import { fetchModules } from "../api/modules";
import { apiFetch } from "../api/api"; // <-- Add this import

// --- Helpers for token management ---
async function refreshAccessToken() {
  const refresh = localStorage.getItem("refresh");
  if (!refresh) throw new Error("No refresh token");
  const res = await fetch(`${API_BASE_URL}${API_ROUTES.tokenRefresh}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) throw new Error("Session expired or invalid refresh token");
  const data = await res.json();
  if (!data.access) throw new Error("No access token in refresh response");
  localStorage.setItem("access", data.access);
  // If backend rotates refresh tokens, persist the new refresh token too.
  if (data.refresh) {
    localStorage.setItem("refresh", data.refresh);
    try {
      const storedUser = JSON.parse(localStorage.getItem("user"));
      if (storedUser && typeof storedUser === "object") {
        localStorage.setItem(
          "user",
          JSON.stringify({ ...storedUser, refresh: data.refresh })
        );
      }
    } catch {
      // Ignore storage sync errors.
    }
  }
  // Optionally update user state if needed
  return data.access;
}

// --- Auth Context ---
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tablesByModule, setTablesByModule] = useState({});

  // --- Timers and refs ---
  const inactivityTimeout = 60 * 60 * 1000; // 1 hour
  const refreshIntervalMs = 10 * 60 * 1000; // 10 minutes
  const inactivityTimerRef = useRef();
  const refreshTimerRef = useRef();
  const loginInFlightRef = useRef(false);

  // Debug helper
  const debug = (...args) => { if (import.meta.env.DEV) console.log("[Auth]", ...args); };

  // --- Local Storage Sync on mount ---
  useEffect(() => {
    try {
      const storedUser = JSON.parse(localStorage.getItem("user"));
      const storedProjects = JSON.parse(localStorage.getItem("projects"));
      const storedContext = JSON.parse(localStorage.getItem("context"));
      if (storedUser?.token) setUser(storedUser);
      if (Array.isArray(storedProjects)) setProjects(storedProjects);
      if (storedContext) setContext(storedContext);
    } catch {}
    setLoading(false);
  }, []);

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

    // --- Cleanup on unmount/logout ---
    return () => {
      ["mousemove", "keydown", "mousedown", "touchstart"].forEach(e =>
        window.removeEventListener(e, resetTimers)
      );
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
    // eslint-disable-next-line
  }, [user]);

  // --- Refetch tables when context changes ---
  useEffect(() => {
    if (user && context?.modules && context?.projectId) {
      refetchTables();
    }
    // eslint-disable-next-line
  }, [user, context?.modules, context?.projectId]);

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
      const res = await fetch(`${API_BASE_URL}${API_ROUTES.token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      const { access, refresh } = await res.json();

      // Fetch roles
      const rolesRes = await fetch(`${API_BASE_URL}${API_ROUTES.myRoles}`, {
        headers: { Authorization: `Bearer ${access}` },
      });
      if (!rolesRes.ok) throw new Error("Failed to fetch user roles");
      const { roles } = await rolesRes.json();

      // Build project map
      const projectMap = {};
      for (const r of roles) {
        if (
          r.project_id &&
          r.project &&
          (r.context_type === "project" || r.context_type === "module")
        ) {
          projectMap[r.project_id] = { id: r.project_id, name: r.project };
        }
      }
      for (const r of roles) {
        if (r.context_type === "module" && (!r.project_id || !r.project)) {
          if (import.meta.env.DEV) {
            console.warn("[Auth] Module-level role missing project info:", r);
          }
        }
      }
      const projectsArr = Object.values(projectMap);

      const userObj = { username, token: access, refresh, roles };
      setUser(userObj);
      setProjects(projectsArr);
      localStorage.setItem("user", JSON.stringify(userObj));
      localStorage.setItem("projects", JSON.stringify(projectsArr));
      localStorage.setItem("access", access);
      localStorage.setItem("refresh", refresh);
      localStorage.removeItem("context");
      setContext(null);

      debug("Login success", userObj, projectsArr);

      // If only one project, auto-select it
      if (projectsArr.length === 1) {
        await selectProject(projectsArr[0].id, userObj, projectsArr);
        loginInFlightRef.current = false;
        setLoading(false);
        return { requireProjectSelection: false };
      } else {
        setContext(null);
        localStorage.removeItem("context");
        loginInFlightRef.current = false;
        setLoading(false);
        return { requireProjectSelection: true };
      }
    } catch (err) {
      setLoading(false);
      loginInFlightRef.current = false;
      throw err;
    }
  };

  // --- Select a project: build context, fetch modules ---
  const selectProject = async (projectId, _user = user, _projects = projects) => {
    setLoading(true);
    try {
      const project = (_projects || projects).find(p => String(p.id) === String(projectId));
      if (!project) throw new Error("Invalid project selection");

      const projectRoles = (_user || user).roles.filter(r =>
        ((r.context_type === "project" && String(r.project_id) === String(projectId)) ||
          (r.context_type === "module" && String(r.project_id) === String(projectId)))
      );
      const modules = await fetchModules((_user || user).token, projectId);

      const ctx = {
        projectId,
        project,
        projectRoles,
        modules,
      };
      setContext(ctx);
      localStorage.setItem("context", JSON.stringify(ctx));
      debug("Project selected and context built", ctx);
      setLoading(false);
      return true;
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  // --- Logout: clear all state, timers, and storage ---
  const logout = async (reason) => {
    debug("Logout called:", reason);

    // Best-effort backend logout (blacklist refresh token). Always continue local logout.
    try {
      const refresh = localStorage.getItem("refresh");
      const access = localStorage.getItem("access");
      if (refresh && access && API_ROUTES.logout) {
        await fetch(`${API_BASE_URL}${API_ROUTES.logout}`, {
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
      await Promise.all(
        context.modules.map(async (mod) => {
          try {
            // Use apiFetch for auto JWT refresh
            const tables = await apiFetch(API_ROUTES.tables, {
              project_id: context.projectId,
              module_id: mod.id,
              token: user.token, // optional, apiFetch can also use localStorage
            });
            grouped[String(mod.id)] = tables;
          } catch (err) {
            // Optionally, handle unauthorized (if still fails), or set as empty
            grouped[String(mod.id)] = [];
            if (import.meta.env.DEV) console.error("Failed to fetch tables for module", mod.id, err);
          }
        })
      );
      setTablesByModule(grouped);
    } catch (err) {
      setTablesByModule({});
      if (import.meta.env.DEV) console.error("Failed to fetch tables", err);
    }
  };

  // --- Role helpers ---
  const hasRole = (roleName) =>
    context?.projectRoles?.some(r => r.role === roleName);

  const canSchemaAdmin = () =>
    context?.projectRoles?.some(r => r.role === "admins_group" || r.role === "admin");

  const canManageAllModules = () =>
    context?.projectRoles?.some(r => ["admins_group", "admin", "auditors_group", "auditor"].includes(r.role));

  const canManageAssignedModules = () =>
    context?.projectRoles?.some(r => r.role === "dataowners_group" || r.role === "dataowner");

  return (
    <AuthContext.Provider
      value={{
        user,
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);