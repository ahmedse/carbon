import React from "react";
import { Box, Typography } from "@mui/material";

const Footer = () => (
  <Box
    component="footer"
    sx={{
      py: 2,
      px: 2,
      mt: "auto",
      backgroundColor: (theme) => theme.palette.grey[200],
      textAlign: "center",
    }}
  >
    <Typography variant="body2" color="textSecondary">
      &copy; {new Date().getFullYear()} Carbon Platform
    </Typography>
  </Box>
);

export default Footer;