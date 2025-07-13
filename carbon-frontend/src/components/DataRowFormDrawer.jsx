// File: src/components/DataRowFormDrawer.jsx

import React, { useState, useEffect } from "react";
import {
  Box, TextField, MenuItem, Checkbox, FormControlLabel, Button, Typography
} from "@mui/material";
import FileCellRenderer from "./FileCellRenderer";
import { DatePicker } from "@mui/x-date-pickers";
import dayjs from "dayjs";
import { useNotification } from "./NotificationProvider";

function coerceValue(field, value) {
  // Coerce to correct JS type based on field.type
  if (field.type === "number") {
    if (value === "" || value === null || value === undefined) return null;
    const num = Number(value);
    return isNaN(num) ? value : num;
  }
  if (field.type === "boolean") {
    return Boolean(value);
  }
  if (field.type === "multiselect") {
    return Array.isArray(value) ? value : value ? [value] : [];
  }
  if (field.type === "date") {
    if (!value) return null;
    if (typeof value === "string") return dayjs(value);
    return value;
  }
  return value;
}

// Helper to validate a single value based on field config and type
function validateField(field, value, values) {
  if (field.required) {
    // Handle emptiness for each field type
    if (
      value === "" ||
      value === null ||
      value === undefined ||
      (Array.isArray(value) && value.length === 0)
    ) {
      return `${field.label} is required.`;
    }
  }
  // Type-specific validation
  if (field.type === "number") {
    if (value !== null && value !== undefined && value !== "") {
      if (typeof value === "string" && value.trim() === "") {
        return `${field.label} is required.`;
      }
      const num = Number(value);
      if (isNaN(num)) {
        return `${field.label} must be a number (e.g. 123).`;
      }
      if (num < 0) {
        return `${field.label} cannot be negative. Please enter zero or a positive number.`;
      }
    }
  }
  if (field.type === "boolean") {
    if (typeof value !== "boolean") {
      return `${field.label} must be true or false (checkbox).`;
    }
  }
  if (field.type === "select") {
    const allowed = (field.options || []).map(opt => opt.value);
    if (value && !allowed.includes(value)) {
      return `${field.label} must be one of: ${allowed.join(', ')}.`;
    }
  }
  if (field.type === "multiselect") {
    const allowed = (field.options || []).map(opt => opt.value);
    if (!Array.isArray(value)) {
      return `${field.label} must be a list (select one or more).`;
    }
    const invalid = value.filter(v => !allowed.includes(v));
    if (invalid.length > 0) {
      return `${field.label} contains invalid values: ${invalid.join(', ')}. Allowed: ${allowed.join(', ')}.`;
    }
  }
  if (field.type === "date") {
    if (value && !dayjs(value).isValid()) {
      return `${field.label} must be a valid date.`;
    }
  }
  // Custom (JSON) validation
  if (field.validation) {
    try {
      const rules =
        typeof field.validation === "string"
          ? JSON.parse(field.validation)
          : field.validation;
      // Regex for string input
      if (rules.regex && typeof value === "string" && value) {
        const re = new RegExp(rules.regex);
        if (!re.test(value))
          return rules.message || `Invalid format.`;
      }
      // Number: min/max
      if (field.type === "number" && value !== null && value !== undefined && value !== "") {
        const num = Number(value);
        if (rules.min !== undefined && num < rules.min)
          return `${field.label} must be at least ${rules.min}.`;
        if (rules.max !== undefined && num > rules.max)
          return `${field.label} must be at most ${rules.max}.`;
      }
      // String: min/max length
      if (typeof value === "string") {
        if (
          rules.minLength !== undefined &&
          value.length < rules.minLength
        )
          return `${field.label} must be at least ${rules.minLength} characters.`;
        if (
          rules.maxLength !== undefined &&
          value.length > rules.maxLength
        )
          return `${field.label} must be at most ${rules.maxLength} characters.`;
      }
      // Array: minItems/maxItems
      if (Array.isArray(value)) {
        if (
          rules.minItems !== undefined &&
          value.length < rules.minItems
        )
          return `${field.label}: select at least ${rules.minItems}.`;
        if (
          rules.maxItems !== undefined &&
          value.length > rules.maxItems
        )
          return `${field.label}: select at most ${rules.maxItems}.`;
      }
    } catch (e) {
      // ignore validation parse error
    }
  }
  return null;
}

export default function DataRowFormDrawer({
  open,
  onClose,
  fields = [],
  initial,
  onSubmit,
  token,
  project_id,
  module_id,
  uploadRowFile,
  rowId,
  mode,
}) {
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const notifyContext = useNotification();
  // Defensive: ensure notify is always a function
  const notify = (notifyContext && typeof notifyContext.notify === "function")
    ? notifyContext.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  useEffect(() => {
    // Coerce all initial values to correct types
    const initialVals = (initial?.values || {});
    const newVals = {};
    (fields || []).forEach(field => {
      newVals[field.name] = coerceValue(field, initialVals[field.name]);
    });
    setValues(newVals);
    setErrors({});
  }, [initial, fields]);

  const handleChange = (fieldName, value) => {
    const field = fields.find(f => f.name === fieldName);
    if (!field) return;
    // Always coerce value to correct type before storing
    const coerced = coerceValue(field, value);
    setValues((prev) => ({ ...prev, [fieldName]: coerced }));
    // Re-validate the field
    setErrors((prev) => ({ ...prev, [fieldName]: validateField(field, coerced, values) }));
  };

  const validateAll = () => {
    const newErrors = {};
    (fields || []).forEach((field) => {
      if (!field.is_active) return;
      const val = coerceValue(field, values[field.name]);
      const err = validateField(field, val, values);
      if (err) newErrors[field.name] = err;
    });
    setErrors(newErrors);
    return newErrors;
  };

  const handleSubmit = async () => {
    const newErrors = validateAll();
    if (Object.keys(newErrors).length) {
      notify({ message: "Please fix the errors in the form (see highlighted fields).", type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      // Prepare submission values with correct types
      const submitVals = {};
      (fields || []).forEach((f) => {
        let val = values[f.name];
        // For date: send as ISO string or null
        if (f.type === "date" && val) {
          if (typeof val === "string") {
            val = dayjs(val).isValid() ? dayjs(val).toISOString() : null;
          } else if (val && typeof val.toISOString === "function") {
            val = val.toISOString();
          } else {
            val = null;
          }
        }
        // For number: send as number, or null
        if (f.type === "number") {
          val = val === "" || val === null || val === undefined ? null : Number(val);
        }
        // For boolean: ensure boolean
        if (f.type === "boolean") {
          val = !!val;
        }
        submitVals[f.name] = val;
      });
      await onSubmit(submitVals, rowId);
    } catch (err) {
      // Parse backend error for user-friendly message
      let msg = err?.message || "Failed to save row";
      if (err?.response?.data) {
        // DRF error: {field: [error]}
        const backendErrors = err.response.data;
        const firstField = Object.keys(backendErrors)[0];
        const firstErr = backendErrors[firstField]?.[0];
        msg = `${firstField}: ${firstErr}`;
        setErrors(prev => ({ ...prev, [firstField]: firstErr }));
      }
      notify({ message: msg, type: "error" });
    }
    setSubmitting(false);
  };

  return (
    <Box width="100%">
      <Box display="flex" flexDirection="column" gap={2} p={1}>
        {(fields || []).map((field) => {
          if (!field.is_active) return null;
          const fieldError = errors[field.name];
          const commonProps = {
            label: field.label + (field.required ? " *" : ""),
            value:
              values[field.name] ??
              (field.type === "multiselect" ? [] : ""),
            onChange: (e) =>
              handleChange(
                field.name,
                field.type === "boolean"
                  ? e.target.checked
                  : field.type === "multiselect"
                  ? e.target.value
                  : e.target.value
              ),
            error: !!fieldError,
            helperText: fieldError,
            fullWidth: true,
            required: !!field.required,
            disabled: submitting,
            inputProps: {},
          };

          if (field.type === "number") {
            commonProps.inputProps.inputMode = "decimal";
            commonProps.inputProps.pattern = "[0-9]*";
          }

          if (field.type === "string" || field.type === "number") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                type={field.type === "number" ? "number" : "text"}
              />
            );
          }
          if (field.type === "text") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                multiline
              />
            );
          }
          if (field.type === "boolean") {
            return (
              <FormControlLabel
                key={field.name}
                control={
                  <Checkbox
                    checked={!!values[field.name]}
                    onChange={commonProps.onChange}
                    disabled={submitting}
                  />
                }
                label={field.label + (field.required ? " *" : "")}
              />
            );
          }
          if (field.type === "date") {
            return (
              <DatePicker
                key={field.name}
                label={field.label + (field.required ? " *" : "")}
                value={
                  values[field.name]
                    ? dayjs(values[field.name])
                    : null
                }
                onChange={(val) => handleChange(field.name, val)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    error: !!fieldError,
                    helperText: fieldError,
                    required: !!field.required,
                  },
                }}
                disabled={submitting}
              />
            );
          }
          if (field.type === "select") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                select
              >
                {(field.options || []).map((opt) => (
                  <MenuItem value={opt.value} key={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </TextField>
            );
          }
          if (field.type === "multiselect") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                select
                SelectProps={{ multiple: true }}
              >
                {(field.options || []).map((opt) => (
                  <MenuItem value={opt.value} key={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </TextField>
            );
          }
          if (field.type === "file") {
            // Only allow file upload if editing existing row
            if (!rowId && mode === "add") {
              return (
                <Box
                  key={field.name}
                  display="flex"
                  alignItems="center"
                  gap={2}
                >
                  <Typography variant="body2" color="textSecondary">
                    {field.label}: Save row before uploading file.
                  </Typography>
                </Box>
              );
            }
            return (
              <FileCellRenderer
                key={field.name}
                value={values[field.name]}
                onChange={(val) => handleChange(field.name, val)}
                rowId={rowId}
                fieldName={field.name}
                uploadRowFile={uploadRowFile}
                token={token}
                project_id={project_id}
                module_id={module_id}
                disabled={submitting}
              />
            );
          }
          return null;
        })}
      </Box>
      <Box display="flex" gap={2} mt={2}>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting}
        >
          Save
        </Button>
      </Box>
    </Box>
  );
}