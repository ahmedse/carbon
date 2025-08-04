// src/pages/Help.jsx

import React from "react";
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
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
import BugReportIcon from "@mui/icons-material/BugReport";
import FeedbackIcon from "@mui/icons-material/Feedback";
import InsightsIcon from "@mui/icons-material/Insights";
import AddCircleIcon from "@mui/icons-material/AddCircle";
import TableRowsIcon from "@mui/icons-material/TableRows";
import EditIcon from "@mui/icons-material/Edit";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import DashboardIcon from "@mui/icons-material/Dashboard";
import EmojiObjectsIcon from "@mui/icons-material/EmojiObjects";
import StarIcon from "@mui/icons-material/Star";

const steps = [
  {
    label: "Select a Project",
    icon: <DashboardIcon />,
    description:
      "After logging in, choose your working project from the project list. All your data and modules are organized by project.",
  },
  {
    label: "Navigate Modules & Tables",
    icon: <TableRowsIcon />,
    description:
      "Use the sidebar to access modules (such as Water, Transportation). Each module contains data tables tailored to your organization's process.",
  },
  {
    label: "Add or Edit Data",
    icon: <AddCircleIcon />,
    description:
      "Within any table, use the 'Add Row' button to enter new data. Click the edit icon to change existing rows, or the trash icon to delete.",
  },
  {
    label: "Analyze & Export",
    icon: <InsightsIcon />,
    description:
      "Use filters and search to analyze your records. Export data to CSV for reporting or further analysis.",
  },
  {
    label: "Track Progress & Collaborate",
    icon: <StarIcon />,
    description:
      "Review data completeness, collaborate with your team, and provide feedback to continuously improve the platform.",
  },
];

const faqs = [
  {
    q: "How do I create a new table or module?",
    a: "If you have admin permissions, use the Schema Manager in the sidebar to add new modules or tables. Define fields, types, and access controls so your team can start entering data immediately."
  },
  {
    q: "Can I edit or delete data after saving?",
    a: "Yes. Click the edit (✎) icon next to a row to update its data. Use the trash (🗑️) icon to delete a row. All changes are tracked for data integrity."
  },
  {
    q: "How do I export my data?",
    a: "Inside any table, use the 'Export CSV' option (usually in the table toolbar or via the bulk actions menu) to download your data for reporting."
  },
  {
    q: "How is access controlled?",
    a: "Access is managed by your project administrator. Roles such as admin, data owner, or auditor determine what you can view or edit in each project/module."
  },
  {
    q: "Who do I contact for support?",
    a: "Use the Feedback page in the sidebar to send questions, bug reports, or suggestions, or email support directly at ahmed.saied@aast.edu."
  },
];

export default function Help() {
  return (
    <Box maxWidth={900} mx="auto" mt={6} mb={8}>
      <Paper elevation={4} sx={{ p: { xs: 2, sm: 4 }, borderRadius: 4, position: "relative", overflow: "hidden" }}>
        {/* Title & Intro */}
        <Box display="flex" alignItems="center" mb={2}>
          <HelpOutlineIcon color="primary" sx={{ fontSize: 48, mr: 2 }} />
          <Typography variant="h3" fontWeight={800} color="primary.dark" letterSpacing={-1}>
            Welcome to the Carbon Data Platform
          </Typography>
        </Box>
        <Typography variant="h5" mb={2} fontWeight={500}>
          Your collaborative tool for carbon data collection, organization, and analysis.
        </Typography>
        <Typography variant="body1" mb={3} color="text.secondary">
          This guide walks you through the essential steps to manage your environmental data, from entering information to analyzing and exporting results.
        </Typography>
        <Divider sx={{ my: 3 }} />

        {/* System Summary Cards */}
        <Grid container spacing={2} mb={2}>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: "#e3f2fd", borderRadius: 3 }}>
              <CardContent sx={{ textAlign: "center" }}>
                <Avatar sx={{ bgcolor: "#1976d2", mx: "auto", mb: 1 }}>
                  <DashboardIcon />
                </Avatar>
                <Typography fontWeight={700}>Unified Workspace</Typography>
                <Typography fontSize={14} color="text.secondary">All your modules, tables, and data in one place. Switch projects with a single click.</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: "#e8f5e9", borderRadius: 3 }}>
              <CardContent sx={{ textAlign: "center" }}>
                <Avatar sx={{ bgcolor: "#43a047", mx: "auto", mb: 1 }}>
                  <EmojiObjectsIcon />
                </Avatar>
                <Typography fontWeight={700}>Smart Data Entry</Typography>
                <Typography fontSize={14} color="text.secondary">Flexible forms, field validation, and attachments let you capture the data that matters.</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: "#f3e5f5", borderRadius: 3 }}>
              <CardContent sx={{ textAlign: "center" }}>
                <Avatar sx={{ bgcolor: "#8e24aa", mx: "auto", mb: 1 }}>
                  <InsightsIcon />
                </Avatar>
                <Typography fontWeight={700}>Instant Insights</Typography>
                <Typography fontSize={14} color="text.secondary">Use filters and export tools to turn your data into actionable reports.</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Workflow Stepper */}
        <Typography variant="h5" mt={4} mb={2} fontWeight={700}>
          Typical Workflow: Step by Step
        </Typography>
        <Stepper orientation="vertical" activeStep={-1} sx={{ bgcolor: "#f9fbe7", borderRadius: 2, p: 2, mb: 4 }}>
          {steps.map((step, idx) => (
            <Step key={step.label} completed>
              <StepLabel
                icon={
                  <Tooltip title={step.label}>
                    <Avatar sx={{ bgcolor: idx === 0 ? "#1976d2" : idx === 1 ? "#0288d1" : idx === 2 ? "#43a047" : idx === 3 ? "#fbc02d" : "#8e24aa" }}>
                      {step.icon}
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
          ))}
        </Stepper>

        {/* User Story */}
        <Divider sx={{ my: 3 }} />
        <Typography variant="h5" fontWeight={700} mb={1}>User Story: A Day in the Carbon Platform</Typography>
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 4, bgcolor: "#fff8e1" }}>
          <Typography variant="body1" mb={1}>
            <b>Meet Omar, a sustainability officer:</b>
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={1}>
            <b>Morning:</b> Omar logs in, selects his project, and checks for any pending data entries.
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={1}>
            <b>Midday:</b> He navigates to the Waste Water module and enters new data from the latest facility report.
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={1}>
            <b>Afternoon:</b> Omar reviews the Water Consumption data, applies filters to spot anomalies, and exports a summary for his manager.
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={1}>
            <b>End of Day:</b> He uses the Feedback page to suggest an improvement to the team.
          </Typography>
        </Paper>

        {/* FAQ Accordion */}
        <Typography variant="h5" fontWeight={700} mb={1}>Frequently Asked Questions</Typography>
        {faqs.map(({ q, a }, i) => (
          <Accordion key={q} sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1" fontWeight={600}>{q}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography fontSize={15}>{a}</Typography>
            </AccordionDetails>
          </Accordion>
        ))}

        {/* Contact & Feedback */}
        <Divider sx={{ my: 3 }} />
        <Box display="flex" alignItems="center" gap={2} mb={2}>
          <ContactSupportIcon color="info" sx={{ fontSize: 32 }} />
          <Typography variant="h6" fontWeight={700}>
            Need help or want to suggest an improvement?
          </Typography>
        </Box>
        <Typography variant="body1" mb={2}>
          • Use the <b>Feedback</b> page to reach our team.<br />
          • Or email us at <a href="mailto:ahmed.saied@aast.edu">ahmed.saied@aast.edu</a>
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Version: 1.0.0 &nbsp; | &nbsp; Last updated: July 2025
        </Typography>
      </Paper>
    </Box>
  );
}