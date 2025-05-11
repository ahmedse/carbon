// src/pages/AdminDashboard/WaterModule.jsx

import React from "react";
import { Box, Typography, Paper } from "@mui/material";

const WaterModule = ({ context }) => (
  <Box>
    <Typography variant="h5" fontWeight={600} mb={2}>
      Water Module
      {context && context.project && <> (Project: {context.project})</>}
      {context && context.cycle && <> (Cycle: {context.cycle})</>}
      {context && context.module && <> (Module: {context.module})</>}
    </Typography>
    <Paper sx={{ p: 3 }}>
      <Typography variant="body1">
        This is the skeleton for the Water module.  
        Add your water management features, statistics, and charts here.
      </Typography>
    </Paper>
  </Box>
);

export default WaterModule;