import React from 'react';
import { Navigate } from 'react-router-dom';

/** Legacy path — Assurance rules live under Excellence. */
export default function AssuranceBoardPage() {
  return <Navigate to="/admin/excellence/rules" replace />;
}
