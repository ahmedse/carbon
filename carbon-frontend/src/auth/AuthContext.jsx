import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";
import { fetchModules } from "../api/modules";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);

  // Debug helper
  const debug = (...args) => { if (import.meta.env.DEV) console.log("[Auth]", ...args); };
  debug("[DEBUG] projects", projects);
  // Inactivity logout timer
  const inactivityTimeout = 60 * 60 * 1000; // 1 hour
  const timerRef = useRef();

  useEffect(() => {
    if (!user) return;
    const reset = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        logout();
        window.location.href = "/login";
      }, inactivityTimeout);
    };
    ["mousemove", "keydown", "mousedown", "touchstart"].forEach(e =>
      window.addEventListener(e, reset)
    );
    reset();
    return () => {
      ["mousemove", "keydown", "mousedown", "touchstart"].forEach(e =>
        window.removeEventListener(e, reset)
      );
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [user]);

  // Load from localStorage on mount
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

  // Login: fetch roles, extract projects, no modules yet
  const login = async ({ username, password }) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}${API_ROUTES.token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      const { access, refresh } = await res.json();

      const rolesRes = await fetch(`${API_BASE_URL}${API_ROUTES.myRoles}`, {
        headers: { Authorization: `Bearer ${access}` },
      });
      if (!rolesRes.ok) throw new Error("Failed to fetch user roles");
      const { roles } = await rolesRes.json();

      // Build a map of unique projects from both project and module scoped roles
      const projectMap = {};

      // Add projects where user has a project-level role
      for (const r of roles) {
        if (
          r.project_id &&
          r.project &&
          (r.context_type === "project" || r.context_type === "module")
        ) {
          // Use project_id as key to deduplicate
          projectMap[r.project_id] = { id: r.project_id, name: r.project };
        }
      }

      // If backend ever sends module roles without project info, log a warning
      for (const r of roles) {
        if (
          r.context_type === "module" &&
          (!r.project_id || !r.project)
        ) {
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
      localStorage.removeItem("context");
      setContext(null);

      debug("Login success", userObj, projectsArr);
      debug("[DEBUG] projectsArr", projectsArr);

      // If only one project, auto-select it
      if (projectsArr.length === 1) {
        debug("[DEBUG] projectsArr", projectsArr);
        await selectProject(projectsArr[0].id, userObj, projectsArr);
        setLoading(false);
        return { requireProjectSelection: false };
      } else {
        setContext(null);
        localStorage.removeItem("context");
        setLoading(false);
        return { requireProjectSelection: true };
      }
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  // Select project: fetch modules for this project only, build context
  const selectProject = async (projectId, _user = user, _projects = projects) => {
    setLoading(true);
    try {
      const project = (_projects || projects).find(p => String(p.id) === String(projectId));
      if (!project) throw new Error("Invalid project selection");

      // Get roles for this project only
      const projectRoles = (_user || user).roles.filter(r =>
        ((r.context_type === "project" && String(r.project_id) === String(projectId)) ||
        (r.context_type === "module" && String(r.project_id) === String(projectId)))
      );

      // Fetch modules for this project only
      const modules = await fetchModules((_user || user).token, projectId);

      const ctx = {
        projectId,
        project,
        projectRoles,
        modules,
      };
      setContext(ctx);
      localStorage.setItem("context", JSON.stringify(ctx));
      debug("[DEBUG] Project selected and context built", ctx);
      debug("Project selected and context built", ctx);
      setLoading(false);
      return true;
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  // Logout: clear all state and storage
  const logout = () => {
    setUser(null);
    setProjects([]);
    setContext(null);
    localStorage.clear();
  };

  // Role helpers
// src/auth/AuthContext.jsx
const hasRole = (roleName) => context?.projectRoles?.some(r => r.role === roleName);

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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);