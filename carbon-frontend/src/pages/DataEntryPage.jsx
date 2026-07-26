// File: src/pages/DataEntryPage.jsx

import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Box } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import TableDataPage from "../components/TableDataPage";
import { PageHeader, LoadingSkeleton } from "../components";

export default function DataEntryPage() {
  const { moduleId, tableId } = useParams();
  const navigate = useNavigate();
  const { user, context } = useAuth();

  if (!user || !context) {
    return <LoadingSkeleton variant="detail" />;
  }

  const projectId = context.project_id || context.projectId;
  const module = (context?.modules || []).find((m) => String(m.id) === String(moduleId));

  return (
    <Box>
      <PageHeader
        title="Data Entry"
        subtitle={module?.name || `Module ${moduleId}`}
        breadcrumbs={[
          { label: "Home", path: "/dashboard" },
          { label: "My Data", path: "/carbon/my-data" },
          { label: module?.name || "...", path: `/carbon/my-data/${moduleId}` },
          { label: "Data Entry" },
        ]}
        actions={
          <Box sx={{ display: "flex", gap: 1 }}>
            <Box
              component="button"
              onClick={() => navigate(`/carbon/my-data/${moduleId}`)}
              sx={{ border: "none", background: "transparent", cursor: "pointer", color: "text.secondary", fontSize: "0.875rem" }}
            >
              Back to source
            </Box>
          </Box>
        }
      />
      <TableDataPage
        project_id={projectId}
        module_id={moduleId}
        moduleId={moduleId}
        tableId={tableId}
        lang={context.language || "en"}
        token={user.token}
      />
    </Box>
  );
}