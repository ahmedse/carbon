// src/i18n/LocaleAwareLocalizationProvider.jsx
// MUI date pickers follow app language (Arabic Day.js locale).
import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';
import 'dayjs/locale/ar';
import 'dayjs/locale/en';
import { useLanguage } from './useLanguage';

export default function LocaleAwareLocalizationProvider({ children }) {
  const { lang } = useLanguage();
  const adapterLocale = lang === 'ar' ? 'ar' : 'en';

  useEffect(() => {
    dayjs.locale(adapterLocale);
  }, [adapterLocale]);

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={adapterLocale}>
      {children}
    </LocalizationProvider>
  );
}

LocaleAwareLocalizationProvider.propTypes = {
  children: PropTypes.node,
};
