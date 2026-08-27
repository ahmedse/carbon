// src/notes/NotesPanel.jsx
// Expanded drawer panel: header (pin + collapse) + tab bar + active tab body.
//
// Tab bar is registry-composed (ADR-0019): the fixed "Notes" tab is always
// first, followed by every contextual inspector tab whose `matches(context)`
// returns true. Today only Notes is registered, so this renders identically to
// the pre-inspector drawer — zero behavior change until tabs are registered.

import React, { useEffect, useMemo, useSyncExternalStore } from 'react';
import { Box, Tabs, Tab, IconButton, Tooltip, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import PushPinIcon from '@mui/icons-material/PushPin';
import { useTranslation } from 'react-i18next';
import { useNotes } from './NotesContext';
import { NotesTab } from './NotesTab';
import {
  tabsFor,
  tabLabel,
  subscribeInspectorTabs,
  getInspectorTabsVersion,
} from '../inspector/InspectorTabRegistry';

export function NotesPanel() {
  const { t } = useTranslation('notes');
  const {
    context, pinned, togglePin, toggleOpen, activeTab, setActiveTab,
  } = useNotes();

  // Re-render whenever tabs register/unregister (registry is non-reactive).
  const tabsVersion = useSyncExternalStore(subscribeInspectorTabs, getInspectorTabsVersion);

  // Contextual tabs auto-discovered from the registry. `tabsVersion` is an
  // intentional extra dependency: it bumps when tabs register/unregister, forcing
  // a recompute even though `context` may be referentially stable.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const contextTabs = useMemo(() => tabsFor(context), [context, tabsVersion]);
  const tabIds = useMemo(
    () => ['notes', ...contextTabs.map((p) => p.id)],
    [contextTabs],
  );

  // If the active tab no longer matches the current context (e.g. navigated
  // away), fall back to Notes.
  useEffect(() => {
    if (activeTab !== 'notes' && !tabIds.includes(activeTab)) {
      setActiveTab('notes');
    }
  }, [activeTab, tabIds, setActiveTab]);

  return (
    <Box
      role="complementary"
      aria-label={t('panel.label')}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.paper',
        borderLeft: '1px solid',
        borderRight: '1px solid',
        borderColor: 'divider',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: 0.2,
          py: 0.1,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Tooltip title={pinned ? t('panel.unpin') : t('panel.pin')}>
          <IconButton size="small" onClick={togglePin} aria-pressed={pinned} sx={{ p: 0.25 }}>
            {pinned ? <PushPinIcon sx={{ fontSize: 14 }} /> : <PushPinOutlinedIcon sx={{ fontSize: 14 }} />}
          </IconButton>
        </Tooltip>
        <Tooltip title={t('panel.collapse')}>
          <IconButton size="small" onClick={toggleOpen} sx={{ p: 0.25 }}>
            <CloseIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
        <Box sx={{ flex: 1 }} />
        <Typography variant="caption" sx={{ pr: 0.75, color: 'text.secondary', fontSize: '0.56rem' }}>
          {t('panel.title')}
        </Typography>
      </Box>

      {/* Tab bar — Notes is the fixed first tab; contextual tabs auto-appended */}
      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        variant="scrollable"
        scrollButtons={false}
        sx={{
          minHeight: 24,
          borderBottom: '1px solid',
          borderColor: 'divider',
          '& .MuiTab-root': { minHeight: 24, py: 0, fontSize: '0.6rem', textTransform: 'none' },
        }}
      >
        <Tab value="notes" label={t('tabs.notes')} />
        {contextTabs.map((provider) => (
          <Tab
            key={provider.id}
            value={provider.id}
            label={tabLabel(provider, t)}
            icon={provider.icon ? <provider.icon sx={{ fontSize: 14 }} /> : undefined}
            iconPosition="start"
          />
        ))}
      </Tabs>

      {/* Active tab body */}
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'notes' && <NotesTab />}
        {contextTabs.map((provider) =>
          activeTab === provider.id ? (
            <Box key={provider.id} sx={{ height: '100%', overflow: 'auto' }}>
              {provider.render(context)}
            </Box>
          ) : null
        )}
      </Box>
    </Box>
  );
}
