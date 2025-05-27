// File: src/components/Footer.jsx
// Path: src/components/Footer.jsx
// Minimal, modern footer.

import React from "react";
import { Box, Typography } from "@mui/material";

export default function Footer() {
  return (
    <Box sx={{ py: 2, textAlign: "center", fontSize: 13, color: "grey.600" }}>
      <Typography variant="body2" color="text.secondary">
        &copy; {new Date().getFullYear()} Carbon Platform. All rights reserved.
      </Typography>
    </Box>
  );
}