import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Box } from "@mui/material";

const AuditorDashboard = () => {
  return (
    <Box display="flex" flexDirection="column" minHeight="100vh">
      <Header />
      <Box component="main" flexGrow={1} p={3}>
        {/* Admin dashboard content here */}
        <h2>Welcome, Auditor!</h2>
      </Box>
      <Footer />
    </Box>
  );
};

export default AuditorDashboard;