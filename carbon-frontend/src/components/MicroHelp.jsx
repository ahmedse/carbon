// src/components/MicroHelp.jsx
// Modular, robust, and i18n-ready contextual help tooltip for forms and UI controls.

import React from "react";
import PropTypes from "prop-types";
import { IconButton, Tooltip } from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { helpTexts } from "../help/helpTexts";

/**
 * MicroHelp - A modular contextual help tooltip with i18n and RTL support.
 *
 * @param {string} helpKey - The lookup key for help text.
 * @param {string} lang - Language code ("en", "ar", etc).
 * @param {object} props - Additional props for IconButton.
 */
export default function MicroHelp({ helpKey, lang = "en", ...props }) {
  // Determine text direction for the current language
  const dir = lang === "ar" ? "rtl" : "ltr";
  // Attempt to find localized help text, fallback to English, else show missing key
  let text = helpTexts[lang]?.[helpKey] ?? helpTexts.en[helpKey];

  // Robust: developer warning if key is missing in all languages
  if (!text) {
    if (import.meta?.env?.DEV || process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.warn(
        `[MicroHelp] Missing help text for key "${helpKey}" in language "${lang}".`
      );
    }
    text = `Help not available for "${helpKey}"`;
  }

  // Security: never render HTML, always plain text
  // Tooltip disables empty string (no icon rendered if no text)
  if (!text) return null;

  return (
    <Tooltip
      title={<span dir={dir}>{text}</span>}
      placement="right"
      arrow
      enterTouchDelay={0}
      leaveTouchDelay={3000}
    >
      <IconButton
        size="small"
        tabIndex={-1}
        aria-label="Show help"
        {...props}
        sx={{
          color: "action.active",
          ...props.sx
        }}
        onClick={e => {
          // Optional: prevent focus on click, but allow keyboard
          if (props.onClick) props.onClick(e);
        }}
      >
        <HelpOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}

MicroHelp.propTypes = {
  helpKey: PropTypes.string.isRequired,
  lang: PropTypes.string,
};