// File: src/components/dashboard/ChartSection.jsx
// Accordion section for charts with expand/collapse

import React from "react";
import { Accordion, AccordionSummary, AccordionDetails, Typography, Box } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

export default function ChartSection({ 
  id: _id, 
  title, 
  subtitle, 
  icon, 
  expanded, 
  onChange, 
  children 
}) {
  return (
    <Accordion
      expanded={expanded}
      onChange={onChange}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: "12px !important",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        "&:before": { display: "none" },
        mb: 2,
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{
          minHeight: 64,
          "&.Mui-expanded": { minHeight: 64 },
          "& .MuiAccordionSummary-content": {
            my: 1.5,
            "&.Mui-expanded": { my: 1.5 },
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, width: "100%" }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              bgcolor: 'success.light',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'success.main',
            }}
          >
            {icon}
          </Box>
          <Box>
            <Typography fontSize="0.9375rem" fontWeight={600} color="text.primary">
              {title}
            </Typography>
            {subtitle && (
              <Typography fontSize="0.75rem" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0, pb: 3, px: 3 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}
