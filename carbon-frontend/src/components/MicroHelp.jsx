import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

const helpTexts = {
  en: {
    "field.order": "Set the position of this field. You can also drag fields to reorder.",
    "field.options": "For select/multiselect fields, add options below as label/value pairs.",
    "field.validation": "You can set validation rules (e.g. required, min, max, regexp). Must be valid JSON.",
    "field.required": "If checked, this field must have a value when entering data.",
    "field.type": "The type determines input (text, number, date, etc). 'Select' will show options.",
    "field.label": "Label seen by users on forms.",
    "field.name": "Internal name (English, no spaces). Used as the key in data.",
    // ...add more as needed
  },
  ar: {
    // Arabic text here for later
  }
};

export default function MicroHelp({ helpKey, lang = "en", ...props }) {
  const dir = lang === "ar" ? "rtl" : "ltr";
  const text = helpTexts[lang]?.[helpKey] || helpTexts.en[helpKey] || "";
  return (
    <Tooltip title={<span dir={dir}>{text}</span>} placement="right" arrow>
      <IconButton size="small" tabIndex={-1} {...props}>
        <HelpOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}