import { useState, useEffect } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';

/**
 * ResizableLayout Component
 * Creates a 3-panel layout: Sidebar | Main Content | AI Copilot Panel
 * The AI panel can be collapsed/expanded and resized
 */
const ResizableLayout = ({ 
  sidebar, 
  mainContent, 
  aiPanel,
  defaultAIPanelWidth = 360,
  minAIPanelWidth = 320,
  maxAIPanelWidth = 600,
}) => {
  const [aiPanelCollapsed, setAIPanelCollapsed] = useState(() => {
    const saved = localStorage.getItem('aiPanelCollapsed');
    return saved ? JSON.parse(saved) : false;
  });
  
  const [aiPanelWidth, setAIPanelWidth] = useState(() => {
    const saved = localStorage.getItem('aiPanelWidth');
    return saved ? parseInt(saved, 10) : defaultAIPanelWidth;
  });

  const [isDragging, setIsDragging] = useState(false);

  // Save state to localStorage
  useEffect(() => {
    localStorage.setItem('aiPanelCollapsed', JSON.stringify(aiPanelCollapsed));
  }, [aiPanelCollapsed]);

  useEffect(() => {
    localStorage.setItem('aiPanelWidth', aiPanelWidth.toString());
  }, [aiPanelWidth]);

  // Handle resize dragging
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= minAIPanelWidth && newWidth <= maxAIPanelWidth) {
        setAIPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, minAIPanelWidth, maxAIPanelWidth]);

  const toggleAIPanel = () => {
    setAIPanelCollapsed(!aiPanelCollapsed);
  };

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Sidebar */}
      {sidebar && (
        <Box
          sx={{
            width: 240,
            flexShrink: 0,
            borderRight: 1,
            borderColor: 'divider',
            overflow: 'auto',
          }}
        >
          {sidebar}
        </Box>
      )}

      {/* Main Content */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {mainContent}
      </Box>

      {/* AI Panel Resize Handle */}
      {!aiPanelCollapsed && (
        <Box
          onMouseDown={handleMouseDown}
          sx={{
            width: 4,
            cursor: 'col-resize',
            bgcolor: isDragging ? 'primary.main' : 'divider',
            transition: 'background-color 0.2s',
            '&:hover': {
              bgcolor: 'primary.light',
            },
            zIndex: 10,
          }}
        />
      )}

      {/* AI Copilot Panel */}
      <Box
        sx={{
          width: aiPanelCollapsed ? 60 : aiPanelWidth,
          flexShrink: 0,
          borderLeft: aiPanelCollapsed ? 0 : 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          transition: 'width 0.3s ease',
          bgcolor: 'background.paper',
        }}
      >
        {/* Collapse/Expand Button */}
        <Tooltip title={aiPanelCollapsed ? 'Expand AI Panel' : 'Collapse AI Panel'}>
          <IconButton
            onClick={toggleAIPanel}
            sx={{
              position: 'absolute',
              top: 8,
              left: -20,
              bgcolor: 'background.paper',
              border: 1,
              borderColor: 'divider',
              zIndex: 20,
              '&:hover': {
                bgcolor: 'action.hover',
              },
            }}
            size="small"
          >
            {aiPanelCollapsed ? <ChevronLeft /> : <ChevronRight />}
          </IconButton>
        </Tooltip>

        {/* AI Panel Content */}
        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          {aiPanel}
        </Box>
      </Box>
    </Box>
  );
};

export default ResizableLayout;
