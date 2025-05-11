// src/pages/AdminDashboard/ElectricityModule.jsx

import React from "react";
import { Box, Typography, Paper } from "@mui/material";

const ElectricityModule = ({ context }) => (
  <Box>
    <Typography variant="h5" fontWeight={600} mb={2}>
      Electricity Module
      {context && context.project && <> (Project: {context.project})</>}
      {context && context.cycle && <> (Cycle: {context.cycle})</>}
      {context && context.module && <> (Module: {context.module})</>}
    </Typography>
    <Paper sx={{ p: 3 }}>
      <Typography variant="body1">
        This is the skeleton for the Electricity module.  
        Add your Electricity management features, statistics, and charts here.
      </Typography>
    </Paper>
  </Box>
);

export default ElectricityModule;