// File: src/pages/NotFound.jsx
// Description: 404 page for unknown routes.

import React from "react";
import { Box, Typography, Button } from "@mui/material";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <Box sx={{ minHeight: "60vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      <Typography variant="h2" color="primary" gutterBottom>
        404
      </Typography>
      <Typography variant="h5" color="text.secondary" gutterBottom>
        Page Not Found
      </Typography>
      <Button variant="contained" component={Link} to="/">
        Go Home
      </Button>
    </Box>
  );
}