// File: src/pages/DataEntryPage.jsx

import React from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import TableDataPage from "../components/TableDataPage";

export default function DataEntryPage() {
  const { moduleName, tableId } = useParams();
  const { user, currentContext } = useAuth();

  if (!user || !currentContext) {
    return <div style={{ padding: 48, textAlign: "center" }}>Loading context...</div>;
  }

  // Always use project_id from context
  const projectId = currentContext.project_id;
  // Prefer module_id from context, else fallback to moduleName (from URL)
  let moduleId = currentContext.module_id;
  if (!moduleId && currentContext.context_type === "module") {
    moduleId = currentContext.context_id;
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
      lang={currentContext.language || "en"}
      token={user.token}
    />
  );
}