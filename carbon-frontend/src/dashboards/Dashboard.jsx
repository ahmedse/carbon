import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Box, Typography, Tabs, Tab, Paper, Button, Alert } from "@mui/material";

// Simulate dynamic data for demo purposes
const fakeModuleData = {
  energy: [{ id: 1, value: 100, note: "Morning" }],
  water: [{ id: 2, value: 60, note: "Noon" }],
  gas: [],
};

export default function Dashboard() {
  const { user, currentContext } = useAuth();
  const [activeModule, setActiveModule] = useState(null);

  console.log("[DEBUG] Current context:", currentContext);
  console.log("[DEBUG] User roles for this context:", user.roles.filter(r => r.project_id === currentContext.context_id));
  
  // Find modules the user can access in this project
  const modules = Array.from(
    new Set(
      user.roles
        .filter(
          r =>
            r.project_id === currentContext.context_id &&
            r.active &&
            r.module &&
            r.permissions &&
            (
              r.permissions.includes("view_data")
            )
        )
        .map(r => r.module)
    )
  );
  // And after modules:
  console.log("[DEBUG] Modules available to user in this project:", modules);


  // If user has no modules, show a message
  if (modules.length === 0) {
    return (
      <Box>
        <Alert severity="warning" sx={{ mt: 4 }}>
          You have no module access in this project.
        </Alert>
      </Box>
    );
  }

  // Auto-select first module if none selected
  const currentModule = activeModule || modules[0];

  // Find role(s) for this module
  const rolesForModule = user.roles.filter(
    r =>
      r.project_id === currentContext.context_id &&
      r.module === currentModule &&
      r.active
  );
  const permissions = Array.from(
    new Set(
      rolesForModule
        .map(r => r.permissions)
        .flat()
        .filter(Boolean)
    )
  );

  // Demo data (replace with real API in prod)
  const entries = fakeModuleData[currentModule] || [];

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Dashboard – {currentContext.project}
      </Typography>
      <Paper sx={{ mb: 2, p: 1 }}>
        <Tabs
          value={currentModule}
          onChange={(_, v) => setActiveModule(v)}
          indicatorColor="primary"
          textColor="primary"
        >
          {modules.map(mod => (
            <Tab label={mod.charAt(0).toUpperCase() + mod.slice(1)} value={mod} key={mod} />
          ))}
        </Tabs>
      </Paper>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6">{currentModule.charAt(0).toUpperCase() + currentModule.slice(1)} Data</Typography>
        {permissions.includes("manage_data") && (
          <Button variant="contained" sx={{ mb: 2 }}>
            Add Entry
          </Button>
        )}
        {entries.length === 0 ? (
          <Typography>No data entries yet.</Typography>
        ) : (
          <Paper sx={{ p: 2 }}>
            {entries.map(entry => (
              <Box key={entry.id} sx={{ mb: 1 }}>
                <Typography>
                  Value: <b>{entry.value}</b> — {entry.note}
                </Typography>
              </Box>
            ))}
          </Paper>
        )}
      </Box>
      <Box>
        <Typography variant="body2" color="text.secondary">
          Your roles in this module: {rolesForModule.map(r => r.role).join(", ")}
        </Typography>
      </Box>
    </Box>
  );
}