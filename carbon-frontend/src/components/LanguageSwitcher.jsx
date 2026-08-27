// src/components/LanguageSwitcher.jsx — ADR-0018 language selector.
// Text-only menu (English / العربية in native script — no flags), mounted in
// HeaderEnhanced next to the avatar menu. Compact and token-driven.
import React, { useState } from 'react';
import { IconButton, Menu, MenuItem, Tooltip } from '@mui/material';
import LanguageIcon from '@mui/icons-material/Language';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../i18n/useLanguage';

// Native-language labels (Google/Apple pattern) — never translated, never flags.
const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
];

export default function LanguageSwitcher() {
  const { lang, setLanguage } = useLanguage();
  // Namespace-first style (ADR-0018): keys are `t('language')` inside the
  // `common` namespace — never `t('common.language')` (i18next v21+ treats
  // the whole string as one key and would render the raw key).
  const { t } = useTranslation('common');
  const [anchorEl, setAnchorEl] = useState(null);

  const handleOpen = (e) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleSelect = (code) => {
    handleClose();
    if (code !== lang) setLanguage(code);
  };

  return (
    <>
      <Tooltip title={t('language')}>
        <IconButton
          size="small"
          aria-label={t('language')}
          aria-haspopup="menu"
          aria-expanded={Boolean(anchorEl)}
          onClick={handleOpen}
          sx={{ color: 'text.secondary' }}
        >
          <LanguageIcon sx={{ fontSize: '1.25rem' }} />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{
          paper: {
            sx: { mt: 0.5, borderRadius: 1.5 },
          },
        }}
      >
        {LANGUAGES.map(({ code, label }) => (
          <MenuItem
            key={code}
            selected={code === lang}
            onClick={() => handleSelect(code)}
          >
            {label}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
