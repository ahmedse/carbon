// File: src/pages/DataEntryPage.jsx

import React from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import TableDataPage from "../components/TableDataPage";

export default function DataEntryPage() {
  const { moduleName, tableId } = useParams();
  const { user, context } = useAuth();

  if (!user || !context) {
    return <div style={{ padding: 48, textAlign: "center" }}>Loading context...</div>;
  }

  // Get project ID robustly
  const projectId = context.project_id || context.projectId;

  // Prefer module_id from context, else fallback to moduleName (from URL)
  let moduleId = context.module_id;
  if (!moduleId && context.context_type === "module") {
    moduleId = context.context_id;
  }
  if (!moduleId && moduleName) {
    moduleId = moduleName;
  }

  return (
    <TableDataPage
      project_id={projectId}
      module_id={moduleId}
      moduleId={moduleId}
      tableId={tableId}
      lang={context.language || "en"}
      token={user.token}
    />
  );
}