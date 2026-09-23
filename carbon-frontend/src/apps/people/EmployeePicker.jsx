import React, { useEffect, useState } from 'react';
import { Autocomplete, TextField } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { fetchEmployees } from '../../api/people';

function labelOf(employee) {
  if (!employee) return '';
  return `${employee.employee_no ?? '—'} — ${employee.full_name ?? ''}`;
}

/**
 * Manager / subject picker. One page of matches, never the full roster.
 */
export default function EmployeePicker({
  token,
  label,
  value,
  onChange,
  excludeId,
  initialLabel,
  required,
}) {
  const { t } = useTranslation('people');
  const [input, setInput] = useState('');
  const [options, setOptions] = useState([]);
  const [selected, setSelected] = useState(() => (
    value ? { id: value, label: initialLabel || String(value) } : null
  ));

  useEffect(() => {
    if (!value) {
      setSelected(null);
      return;
    }
    setSelected((prev) => (
      prev && String(prev.id) === String(value)
        ? prev
        : { id: value, label: initialLabel || String(value) }
    ));
  }, [value, initialLabel]);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    const handle = setTimeout(async () => {
      try {
        const data = await fetchEmployees(token, {
          page: 1,
          page_size: 20,
          q: input.trim(),
        });
        if (cancelled) return;
        const rows = (data?.results || []).filter(
          (employee) => excludeId == null || String(employee.id) !== String(excludeId),
        );
        setOptions(rows.map((employee) => ({
          id: employee.id,
          label: labelOf(employee),
        })));
      } catch {
        if (!cancelled) setOptions([]);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [token, input, excludeId]);

  return (
    <Autocomplete
      size="small"
      options={options}
      value={selected}
      onChange={(_, option) => {
        setSelected(option);
        onChange(option?.id ?? '', option?.label ?? '');
      }}
      onInputChange={(_, next, reason) => {
        if (reason === 'input') setInput(next);
      }}
      getOptionLabel={(option) => option?.label || ''}
      isOptionEqualToValue={(a, b) => String(a?.id) === String(b?.id)}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          placeholder={t('employeeSearchHint')}
        />
      )}
    />
  );
}
