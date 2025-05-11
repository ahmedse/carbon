import React from "react";
import { Box, Typography } from "@mui/material";

function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        py: 2,
        px: 2,
        mt: "auto",
        display: "flex",
        justifyContent: "space-between",
        bgcolor: "background.paper",
        borderTop: "1px solid #e0e0e0",
      }}
    >
      <Typography variant="caption" color="text.secondary">
        © {new Date().getFullYear()} AAST - Carbon Platform
      </Typography>
      <Typography variant="caption" color="text.secondary">
        v0.1
      </Typography>
    </Box>
  );
}

export default Footer;