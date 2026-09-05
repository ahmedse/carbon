// src/help/HelpDocRenderer.jsx
// Pure presentational renderer for a help document (see src/help/helpDocs.js).
// Platform help and every app help render through this single component.

import React from "react";
import {
  Box,
  Typography,
  Paper,
  Divider,
  Stepper,
  Step,
  StepLabel,
  Grid,
  Card,
  CardContent,
  Avatar,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import ContactSupportIcon from "@mui/icons-material/ContactSupport";
import InsightsIcon from "@mui/icons-material/Insights";
import AddCircleIcon from "@mui/icons-material/AddCircle";
import TableRowsIcon from "@mui/icons-material/TableRows";
import DashboardIcon from "@mui/icons-material/Dashboard";
import EmojiObjectsIcon from "@mui/icons-material/EmojiObjects";
import StarIcon from "@mui/icons-material/Star";
import AppsIcon from "@mui/icons-material/Apps";

// Icon token → MUI icon (kept in the renderer so help docs stay pure data).
const ICONS = {
  workspace: DashboardIcon,
  data: EmojiObjectsIcon,
  insights: InsightsIcon,
  project: DashboardIcon,
  navigate: TableRowsIcon,
  add: AddCircleIcon,
  export: InsightsIcon,
  collaborate: StarIcon,
  app: AppsIcon,
};

const STEP_COLORS = ["primary.dark", "info.dark", "success.main", "warning.main", "secondary.main"];

/** Renders a single help document (doc shape from helpDocs.js). */
export default function HelpDocRenderer({ doc }) {
  if (!doc) return null;

  const contact = doc.contact || null;

  return (
    <Box maxWidth={900} mx="auto" mt={6} mb={8}>
      <Paper elevation={4} sx={{ p: { xs: 2, sm: 4 }, borderRadius: 4, position: "relative", overflow: "hidden" }}>
        {/* Title & Intro */}
        <Box display="flex" alignItems="center" mb={2}>
          <HelpOutlineIcon color="primary" sx={{ fontSize: '3rem', mr: 2 }} />
          <Typography variant="h3" fontWeight={800} color="primary.dark" letterSpacing={-1}>
            {doc.title}
          </Typography>
        </Box>
        <Typography variant="h5" mb={2} fontWeight={500}>
          {doc.intro}
        </Typography>
        <Typography variant="body1" mb={3} color="text.secondary">
          {doc.description}
        </Typography>
        <Divider sx={{ my: 3 }} />

        {/* Summary Cards */}
        {(doc.cards?.length || 0) > 0 && (
          <Grid container spacing={2} mb={2}>
            {(doc.cards || []).map((card, idx) => {
              const CardIcon = ICONS[card.icon] || DashboardIcon;
              const colors = ["primary.light", "success.light", "secondary.light"];
              return (
                <Grid key={card.title} size={{ xs: 12, sm: 4 }}>
                  <Card sx={{ bgcolor: (t) => t.palette[colors[idx % colors.length]] || t.palette.primary.light, borderRadius: 3, height: "100%" }}>
                    <CardContent sx={{ textAlign: "center" }}>
                      <Avatar sx={{ bgcolor: idx === 1 ? "success.main" : idx === 2 ? "secondary.main" : "primary.main", mx: "auto", mb: 1 }}>
                        <CardIcon />
                      </Avatar>
                      <Typography fontWeight={700}>{card.title}</Typography>
                      <Typography fontSize={14} color="text.secondary">{card.description}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        )}

        {/* Workflow Stepper */}
        {(doc.steps?.length || 0) > 0 && (
          <>
            <Typography variant="h5" mt={4} mb={2} fontWeight={700}>
              Typical Workflow: Step by Step
            </Typography>
            <Stepper orientation="vertical" activeStep={-1} sx={{ bgcolor: 'background.dark', borderRadius: 2, p: 2, mb: 4 }}>
              {(doc.steps || []).map((step, idx) => {
                const StepIcon = ICONS[step.icon] || DashboardIcon;
                return (
                  <Step key={step.label} completed>
                    <StepLabel
                      icon={
                        <Tooltip title={step.label}>
                          <Avatar sx={{ bgcolor: STEP_COLORS[idx % STEP_COLORS.length] }}>
                            <StepIcon />
                          </Avatar>
                        </Tooltip>
                      }
                      sx={{ mb: 1 }}
                    >
                      <Typography variant="h6" fontWeight={600}>{step.label}</Typography>
                    </StepLabel>
                    <Box ml={7} mb={2}>
                      <Typography fontSize={15} color="text.secondary">{step.description}</Typography>
                    </Box>
                  </Step>
                );
              })}
            </Stepper>
          </>
        )}

        {/* User Story */}
        {doc.userStory && (
          <>
            <Divider sx={{ my: 3 }} />
            <Typography variant="h5" fontWeight={700} mb={1}>{doc.userStory.title}</Typography>
            <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 4, bgcolor: 'background.dark' }}>
              <Typography variant="body1" mb={1}>
                <b>{doc.userStory.character}</b>
              </Typography>
              {(doc.userStory.scenes || []).map((scene) => (
                <Typography key={scene.time} variant="body2" color="text.secondary" mb={1}>
                  <b>{scene.time}:</b> {scene.text}
                </Typography>
              ))}
            </Paper>
          </>
        )}

        {/* FAQ Accordion */}
        {(doc.faqs?.length || 0) > 0 && (
          <>
            <Typography variant="h5" fontWeight={700} mb={1}>Frequently Asked Questions</Typography>
            {(doc.faqs || []).map(({ q, a }) => (
              <Accordion key={q} sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1" fontWeight={600}>{q}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography fontSize={15}>{a}</Typography>
                </AccordionDetails>
              </Accordion>
            ))}
          </>
        )}

        {/* Contact & Feedback */}
        {contact && (
          <>
            <Divider sx={{ my: 3 }} />
            <Box display="flex" alignItems="center" gap={2} mb={2}>
              <ContactSupportIcon color="info" sx={{ fontSize: '2rem' }} />
              <Typography variant="h6" fontWeight={700}>
                {contact.intro}
              </Typography>
            </Box>
            <Typography variant="body1" mb={2}>
              • Use the <b>Feedback</b> page to reach our team.<br />
              • Or email us at <a href={`mailto:${contact.email}`}>{contact.email}</a>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Version: {contact.version} &nbsp; | &nbsp; Last updated: {contact.lastUpdated}
            </Typography>
          </>
        )}
      </Paper>
    </Box>
  );
}
