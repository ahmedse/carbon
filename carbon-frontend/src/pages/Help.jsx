// src/pages/Help.jsx

import React from "react";
import { Box, Typography, Paper, List, ListItem, ListItemIcon, ListItemText, Divider } from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import ContactSupportIcon from "@mui/icons-material/ContactSupport";
import BugReportIcon from "@mui/icons-material/BugReport";
import FeedbackIcon from "@mui/icons-material/Feedback";

export default function Help() {
  return (
    <Box maxWidth={700} mx="auto" mt={5}>
      <Paper elevation={3} sx={{ p: 4, borderRadius: 3 }}>
        <Box display="flex" alignItems="center" mb={3}>
          <HelpOutlineIcon color="primary" sx={{ fontSize: 40, mr: 2 }} />
          <Typography variant="h4" fontWeight={700}>
            Help &amp; Documentation
          </Typography>
        </Box>
        <Typography variant="body1" mb={2}>
          Welcome to the Carbon Platform! Here you'll find guidance, documentation, and ways to get support.
        </Typography>
        <Divider sx={{ my: 2 }} />
        <List>
          <ListItem>
            <ListItemIcon><ContactSupportIcon color="info" /></ListItemIcon>
            <ListItemText
              primary="Getting Started"
              secondary={
                <>
                  • Select your project after logging in.<br />
                  • Use the sidebar to access modules, tables, and tools.
                </>
              }
            />
          </ListItem>
          <ListItem>
            <ListItemIcon><HelpOutlineIcon color="info" /></ListItemIcon>
            <ListItemText
              primary="How to add or edit data?"
              secondary={
                <>
                  • Navigate to a module, then select a table.<br />
                  • Use the 'Add Row' button to enter new data, or edit/delete existing rows.
                </>
              }
            />
          </ListItem>
          <ListItem>
            <ListItemIcon><BugReportIcon color="warning" /></ListItemIcon>
            <ListItemText
              primary="Found a bug or have an issue?"
              secondary={
                <>
                  • Please use the <b>Feedback</b> page (see sidebar) to report bugs or suggest improvements.<br />
                  • You can also contact the support team at <a href="mailto:ahmed.saied@aast.edu">ahmed.saied@aast.edu</a>.
                </>
              }
            />
          </ListItem>
          <ListItem>
            <ListItemIcon><FeedbackIcon color="success" /></ListItemIcon>
            <ListItemText
              primary="How do I give feedback?"
              secondary={
                <>
                  • Use the <b>Feedback</b> page to quickly send your suggestions or comments to the development team.<br />
                  • We appreciate your help in making this platform better during development!
                </>
              }
            />
          </ListItem>
        </List>
        <Divider sx={{ my: 2 }} />
        <Typography variant="body2" color="text.secondary">
          Version: 1.0.0 &nbsp; | &nbsp; Last updated: July 2025
        </Typography>
      </Paper>
    </Box>
  );
}