// src/pages/NotFound.jsx
// 404 page for unknown routes.

import React from "react";
import { Box, Typography, Button } from "@mui/material";
import { Link } from "react-router-dom";

/**
 * 404 Not Found page.
 */
export default function NotFound() {
  return (
    <Box sx={{ minHeight: "60vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      <Typography variant="h2" color="primary" gutterBottom>
        404
      </Typography>
      <Typography variant="h5" color="text.secondary" gutterBottom>
        Page Not Found
      </Typography>
      <Button variant="contained" component={Link} to="/" sx={{ mt: 2 }}>
        Go Home
      </Button>
    </Box>
  );
}