import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AdminDashboard from "./pages/AdminDashboard";
import AuditorDashboard from "./pages/AuditorDashboard";
import DataOwnerDashboard from "./pages/DataOwnerDashboard";

const Router = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/auditor" element={<AuditorDashboard />} />
        <Route path="/data-owner" element={<DataOwnerDashboard />} />
        <Route path="*" element={<div>404 Not Found</div>} />
      </Routes>
    </BrowserRouter>
  );
};

export default Router;