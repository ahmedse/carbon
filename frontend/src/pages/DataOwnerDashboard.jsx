import React from "react";
import { Box } from "@mui/material";

const DataOwnerDashboard = ({ context }) => (
  <Box display="flex" flexDirection="column" minHeight="100vh">
    <Box component="main" flexGrow={1} p={3}>
      <h2>
        Welcome, Data Owner!
        {context && context.project && <> (Project: {context.project})</>}
        {context && context.cycle && <> (Cycle: {context.cycle})</>}
        {context && context.module && <> (Module: {context.module})</>}
      </h2>
      {/* ... */}
    </Box>
  </Box>
);

export default DataOwnerDashboard;