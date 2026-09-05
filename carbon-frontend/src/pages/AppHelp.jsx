// src/pages/AppHelp.jsx
// Per-app help page (route /help/:appId). Resolves the app help doc from
// src/help/helpDocs.js; unknown apps show a friendly not-found state.

import React from "react";
import { useParams, Link } from "react-router-dom";
import { Box, Typography, Paper, Button } from "@mui/material";
import useDocumentTitle from "../hooks/useDocumentTitle";
import HelpDocRenderer from "../help/HelpDocRenderer";
import { getAppHelpDoc } from "../help/helpDocs";

export default function AppHelp() {
  const { appId } = useParams();
  const doc = getAppHelpDoc(appId);
  useDocumentTitle(doc ? doc.title : "Help");

  if (!doc) {
    return (
      <Box maxWidth={900} mx="auto" mt={6} mb={8}>
        <Paper elevation={4} sx={{ p: { xs: 3, sm: 5 }, borderRadius: 4, textAlign: "center" }}>
          <Typography variant="h4" fontWeight={800} gutterBottom>
            Help Not Found
          </Typography>
          <Typography variant="body1" color="text.secondary" mb={3}>
            We couldn't find help for “{appId}”. It may not be an installed application.
          </Typography>
          <Button variant="contained" component={Link} to="/help">
            Back to platform help
          </Button>
        </Paper>
      </Box>
    );
  }

  return <HelpDocRenderer doc={doc} />;
}
