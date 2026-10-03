// src/help/AppGuides.jsx
// Multi-guide view for one app: an Overview plus role guides (for Carbon, the
// Lead guide and the Field guide). The selected guide lives in ?guide=<id> so a
// guide can be linked and shared; unknown ids fall back to the first guide.

import React from "react";
import { useSearchParams } from "react-router-dom";
import { Box, Tab, Tabs } from "@mui/material";

import useDocumentTitle from "../hooks/useDocumentTitle";
import HelpDocRenderer from "./HelpDocRenderer";

export default function AppGuides({ guides }) {
  const [params, setParams] = useSearchParams();
  const rows = Array.isArray(guides) ? guides : [];
  const wanted = params.get("guide");
  const index = Math.max(0, rows.findIndex((row) => row.id === wanted));
  const active = rows[index] || rows[0];

  useDocumentTitle(active ? active.doc.title : "Help");

  if (!active) return null;

  return (
    <Box>
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 1,
          bgcolor: "background.default",
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Tabs
          value={active.id}
          variant="scrollable"
          allowScrollButtonsMobile
          onChange={(_event, value) => setParams({ guide: value }, { replace: true })}
          aria-label="Guides"
          sx={{ maxWidth: 900, mx: "auto", px: { xs: 1, sm: 2 } }}
        >
          {rows.map((row) => (
            <Tab key={row.id} value={row.id} label={row.label} />
          ))}
        </Tabs>
      </Box>
      <HelpDocRenderer doc={active.doc} />
    </Box>
  );
}
