import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Box } from "@mui/material";

const AdminDashboard = ({ context }) => (
  <Box display="flex" flexDirection="column" minHeight="100vh">
    <Header />
    <Box component="main" flexGrow={1} p={3}>
      <h2>
        Welcome, Admin!
        {context && context.project && <> (Project: {context.project})</>}
        {context && context.cycle && <> (Cycle: {context.cycle})</>}
        {context && context.module && <> (Module: {context.module})</>}
      </h2>
      {/* ... */}
    </Box>
    <Footer />
  </Box>
);

export default AdminDashboard;