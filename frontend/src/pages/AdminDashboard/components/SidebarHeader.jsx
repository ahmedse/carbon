// File: frontend/src/pages/AdminDashboard/components/SidebarHeader.jsx
// Purpose: Header for the sidebar, displaying project and cycle info.
// Location: frontend/src/pages/AdminDashboard/components/

import React from "react";
import { Box } from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

/**
 * SidebarHeader component.
 * Displays project and cycle information at the top of the sidebar.
 *
 * @param {string} project - Project name.
 * @param {string} cycle - Cycle name.
 */
const SidebarHeader = ({ project = "AAST Green Campus", cycle = "1 - 2025" }) => {
    return (
    <Box
        sx={{
        p: 1,
        pb: 0.5,
        pt: 1.2,
        display: 'flex',
        alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.10)',
        mb: 1,
        minHeight: 48,
        }}
    >
        <InfoOutlinedIcon sx={{ color: "#aeea00", mr: 1 }} fontSize="small" />
        <Box>
        <Box sx={{ fontWeight: 700, fontSize: 15, color: '#fff', lineHeight: 1.2 }}>
            {project}
        </Box>
        <Box sx={{ fontSize: 12, color: '#bdbdbd', lineHeight: 1.2 }}>
            Cycle: {cycle}
        </Box>
        </Box>
    </Box>
    );
}

export default SidebarHeader;