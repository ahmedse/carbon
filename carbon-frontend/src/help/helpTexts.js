// src/help/helpTexts.js
// Centralized help texts for MicroHelp and other contextual help.
// Easily extendable for i18n.

export const helpTexts = {
  en: {
    "field.order": "Set the position of this field. You can also drag fields to reorder.",
    "field.options": "For select/multiselect fields, add options below as label/value pairs.",
    "field.validation": "You can set validation rules (e.g. required, min, max, regexp). Must be valid JSON.",
    "field.required": "If checked, this field must have a value when entering data.",
    "field.type": "The type determines input (text, number, date, etc). 'Select' will show options.",
    "field.label": "Label seen by users on forms.",
    "field.name": "Internal name (English, no spaces). Used as the key in data.",
    "field.desc": "Internal description (English, no spaces). Used as the field desc in data.",
    "table.desc": "Internal description (English, no spaces). Used as the table desc in data.",
    "table.title": "Internal title (English, no spaces). Used as the table title in data.",
    
    // ...add more keys as needed
  },
  ar: {
    // Example: "field.order": "حدد موقع هذا الحقل. يمكنك أيضًا سحب الحقول لإعادة الترتيب.",
    // Fill in Arabic strings as needed.
  }
};