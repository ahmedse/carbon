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

  return (
    <TableDataPage
      moduleId={moduleName}
      tableId={tableId}
      lang={currentContext.language || "en"}
      token={user.token}
      context_id={currentContext.context_id}
    />
  );
}