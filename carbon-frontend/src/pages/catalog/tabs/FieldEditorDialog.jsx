import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SystemDialog from '../../../components/SystemDialog';

const FIELD_TYPES = ['string', 'text', 'number', 'date', 'boolean', 'select', 'multiselect', 'file', 'reference'];

function normalizeOptions(options = []) {
  return (options || [])
    .filter(Boolean)
    .map((option) => ({
      value: String(option.value ?? '').trim(),
      label: String(option.label ?? option.value ?? '').trim(),
    }))
    .filter((option) => option.value);
}

export default function FieldEditorDialog({ open, onClose, onSave, field = null, tableId }) {
  const [formData, setFormData] = useState({
    name: '',
    label: '',
    type: 'string',
    required: false,
    description: '',
    order: 1,
  });
  const [options, setOptions] = useState([{ value: '', label: '' }]);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;

    if (field) {
      setFormData({
        name: field.name || '',
        label: field.label || '',
        type: field.type || 'string',
        required: Boolean(field.required),
        description: field.description || '',
        order: field.order ?? 1,
      });
      setOptions(normalizeOptions(field.options).length ? normalizeOptions(field.options) : [{ value: '', label: '' }]);
    } else {
      setFormData({
        name: '',
        label: '',
        type: 'string',
        required: false,
        description: '',
        order: 1,
      });
      setOptions([{ value: '', label: '' }]);
    }
    setErrors({});
  }, [open, field]);

  const needsOptions = useMemo(() => formData.type === 'select' || formData.type === 'multiselect', [formData.type]);

  const updateOption = (index, key, value) => {
    setOptions((prev) => prev.map((option, optionIndex) => (optionIndex === index ? { ...option, [key]: value } : option)));
  };

  const addOption = () => setOptions((prev) => [...prev, { value: '', label: '' }]);
  const removeOption = (index) => setOptions((prev) => prev.filter((_, optionIndex) => optionIndex !== index));

  const validate = () => {
    const nextErrors = {};
    const trimmedName = formData.name.trim();
    const trimmedLabel = formData.label.trim();

    if (!trimmedName) nextErrors.name = 'Name is required';
    if (trimmedName.length > 50) nextErrors.name = 'Name must be 50 characters or fewer';
    if (!trimmedLabel) nextErrors.label = 'Label is required';

    if (needsOptions) {
      const validOptions = options.filter((option) => option.value?.trim());
      if (validOptions.length === 0) nextErrors.options = 'Add at least one option';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;

    const payload = {
      data_table: Number(tableId),
      name: formData.name.trim(),
      label: formData.label.trim(),
      type: formData.type,
      required: Boolean(formData.required),
      description: formData.description.trim(),
      order: Number(formData.order || 1),
    };

    if (needsOptions) {
      payload.options = options
        .filter((option) => option.value?.trim())
        .map((option) => ({ value: option.value.trim(), label: option.label.trim() || option.value.trim() }));
    }

    onSave(payload);
  };

  return (
    <SystemDialog
      open={open}
      title={field ? 'Edit Field' : 'Add Field'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      width={640}
      height={560}
      minWidth={520}
      minHeight={420}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          Save Field
        </Button>
      }
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField
            label="Name"
            value={formData.name}
            onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
            required
            error={Boolean(errors.name)}
            helperText={errors.name}
            inputProps={{ maxLength: 50 }}
          />
          <TextField
            label="Label"
            value={formData.label}
            onChange={(event) => setFormData((prev) => ({ ...prev, label: event.target.value }))}
            required
            error={Boolean(errors.label)}
            helperText={errors.label}
          />
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
            <FormControl fullWidth>
              <InputLabel>Type</InputLabel>
              <Select
                value={formData.type}
                label="Type"
                onChange={(event) => setFormData((prev) => ({ ...prev, type: event.target.value }))}
              >
                {FIELD_TYPES.map((fieldType) => (
                  <MenuItem key={fieldType} value={fieldType}>
                    {fieldType}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Order"
              type="number"
              value={formData.order}
              onChange={(event) => setFormData((prev) => ({ ...prev, order: event.target.value }))}
              inputProps={{ min: 1 }}
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="body2" color="text.secondary">
              Mark this field as required
            </Typography>
            <Switch
              checked={Boolean(formData.required)}
              onChange={(event) => setFormData((prev) => ({ ...prev, required: event.target.checked }))}
            />
          </Box>
          <TextField
            label="Description"
            multiline
            rows={3}
            value={formData.description}
            onChange={(event) => setFormData((prev) => ({ ...prev, description: event.target.value }))}
          />

          {needsOptions && (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle2">Options</Typography>
                <Button startIcon={<AddIcon />} onClick={addOption} size="small">
                  Add option
                </Button>
              </Box>
              {errors.options && (
                <Typography color="error" variant="body2" sx={{ mb: 1 }}>
                  {errors.options}
                </Typography>
              )}
              <Stack spacing={1}>
                {options.map((option, index) => (
                  <Box key={`${option.value || 'new'}-${index}`} sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr auto' } }}>
                    <TextField
                      label="Value"
                      value={option.value}
                      onChange={(event) => updateOption(index, 'value', event.target.value)}
                    />
                    <TextField
                      label="Label"
                      value={option.label}
                      onChange={(event) => updateOption(index, 'label', event.target.value)}
                    />
                    <IconButton color="error" onClick={() => removeOption(index)} disabled={options.length === 1}>
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
    </SystemDialog>
  );
}
