import React from "react";
import { useNavigate } from "react-router-dom";
import { Box, Typography, Button } from "@mui/material";

const NotFound = () => {
  const navigate = useNavigate();
  return (
    <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" minHeight="100vh">
      <Typography variant="h3" color="error" gutterBottom>
        404 – Page Not Found
      </Typography>
      <Typography variant="body1" gutterBottom>
        The page you are looking for does not exist.
      </Typography>
      <Button variant="contained" color="primary" onClick={() => navigate("/dashboard")}>
        Go to Dashboard
      </Button>
    </Box>
  );
};

export default NotFound;