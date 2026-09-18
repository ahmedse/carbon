// src/pages/admin/ai/control/ControlHub.jsx
// Shared tabbed shell for Pulse Control Plane destinations (ADR-0036 Phase 1).
import React, { useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Tab, Tabs } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';

/**
 * @param {object} props
 * @param {string} props.title — document + hub title
 * @param {string} props.defaultTab
 * @param {Array<{ id: string, label: string, element: React.ReactElement }>} props.tabs
 */
export default function ControlHub({ title, defaultTab, tabs }) {
  useDocumentTitle(title);
  const [searchParams, setSearchParams] = useSearchParams();

  const activeId = useMemo(() => {
    const fromUrl = searchParams.get('tab');
    if (fromUrl && tabs.some((t) => t.id === fromUrl)) return fromUrl;
    return defaultTab;
  }, [searchParams, tabs, defaultTab]);

  const active = tabs.find((t) => t.id === activeId) || tabs[0];

  const onTabChange = useCallback(
    (_event, nextId) => {
      setSearchParams(nextId === defaultTab ? {} : { tab: nextId }, { replace: true });
    },
    [defaultTab, setSearchParams],
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        width: '100%',
      }}
    >
      <Box
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          px: 1,
          flexShrink: 0,
          bgcolor: 'background.paper',
        }}
      >
        <Tabs
          value={active.id}
          onChange={onTabChange}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          aria-label={title}
        >
          {tabs.map((tab) => (
            <Tab key={tab.id} value={tab.id} label={tab.label} id={`control-tab-${tab.id}`} />
          ))}
        </Tabs>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {active.element}
      </Box>
    </Box>
  );
}

ControlHub.propTypes = {
  title: PropTypes.string.isRequired,
  defaultTab: PropTypes.string.isRequired,
  tabs: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      element: PropTypes.element.isRequired,
    }),
  ).isRequired,
};
