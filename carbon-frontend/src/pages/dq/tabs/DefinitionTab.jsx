// carbon-frontend/src/pages/dq/tabs/DefinitionTab.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Save } from '@mui/icons-material';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import RuleJsonEditor, { validateDefinitionClient, normalizeServerErrors } from '../../../components/dq/RuleJsonEditor';
import { updateDQRule, listDQTags } from '../../../api/dq';
import { fetchAssetProfiles } from '../../../api/catalog';
import { resolveBindings } from '../bindings';

function DefinitionTab({ rule, onChanged }) {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [definitionText, setDefinitionText] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [tables, setTables] = useState([]);
  const [serverErrors, setServerErrors] = useState([]);
  const [saving, setSaving] = useState(false);

  // Sync local state when the rule changes (e.g. after save → new version).
  useEffect(() => {
    setDefinitionText(rule?.definition ? JSON.stringify(rule.definition, null, 2) : '');
    setName(rule?.name || '');
    setDescription(rule?.description || '');
    setSelectedTags((rule?.tags || []).map((t) => t.id));
    setServerErrors([]);
  }, [rule]);

  useEffect(() => {
    let active = true;
    listDQTags(token)
      .then((payload) => {
        if (active) setTags(Array.isArray(payload) ? payload : payload?.results || []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    let active = true;
    fetchAssetProfiles(token)
      .then((payload) => {
        if (!active) return;
        const all = Array.isArray(payload) ? payload : payload?.results || [];
        const unique = [];
        const seen = new Set();
        all.forEach((a) => {
          if (a.data_table != null && !a.data_field && !seen.has(a.data_table)) {
            seen.add(a.data_table);
            unique.push(a);
          }
        });
        setTables(unique);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [token]);

  const bindings = useMemo(() => (rule?.field_assignments || []), [rule]);

  const toggleTag = useCallback((id) => {
    setSelectedTags((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const handleSave = async () => {
    let parsed;
    try {
      parsed = JSON.parse(definitionText);
    } catch (err) {
      setServerErrors([{ field: '_root', code: 'parse', message: `Invalid JSON: ${err.message}` }]);
      return;
    }
    const clientErrors = validateDefinitionClient(parsed);
    if (clientErrors.length) {
      setServerErrors(clientErrors);
      return;
    }
    setSaving(true);
    try {
      const { assignments, errors } = await resolveBindings(parsed, tables, token);
      if (errors.length) {
        setServerErrors(errors);
        return;
      }
      await updateDQRule(token, rule.id, {
        definition: parsed,
        name: name.trim() || parsed.name,
        description,
        tag_ids: selectedTags,
        field_assignments_write: assignments,
      });
      notify({ message: `Rule updated — new version saved`, type: 'success' });
      onChanged?.();
    } catch (err) {
      setServerErrors(normalizeServerErrors(err?.data || err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <Chip size="small" variant="outlined" label={`Version ${rule?.version ?? 1}`} />
        <Chip
          size="small"
          variant="outlined"
          color={rule?.is_active ? 'success' : 'default'}
          label={rule?.is_active ? 'Active' : 'Inactive'}
        />
        {rule?.archived ? <Chip size="small" variant="outlined" color="default" label="Archived" /> : null}
        <Box sx={{ flexGrow: 1 }} />
        <Button
          variant="contained"
          size="small"
          startIcon={<Save />}
          onClick={handleSave}
          disabled={saving || rule?.archived}
        >
          {saving ? 'Saving…' : 'Save Definition'}
        </Button>
      </Stack>

      <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase', mb: 0.5 }}>
        Name & Description
      </Typography>
      <Stack spacing={1.5} sx={{ mb: 2 }}>
        <TextField size="small" label="Rule name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField
          size="small"
          label="Description"
          multiline
          minRows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </Stack>

      <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase', mb: 0.5 }}>
        Tags
      </Typography>
      <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 2 }}>
        {tags.length === 0 ? (
          <Typography sx={{ color: 'text.secondary' }}>No tags configured.</Typography>
        ) : (
          tags.map((tag) => (
            <Chip
              key={tag.id}
              size="small"
              label={tag.name}
              color={selectedTags.includes(tag.id) ? 'primary' : 'default'}
              variant={selectedTags.includes(tag.id) ? 'filled' : 'outlined'}
              onClick={() => toggleTag(tag.id)}
            />
          ))
        )}
      </Stack>

      <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase', mb: 0.5 }}>
        Bindings (from definition)
      </Typography>
      <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 2 }}>
        {bindings.length === 0 ? (
          <Typography sx={{ color: 'text.secondary' }}>
            No table bindings — add them to definition.bindings.
          </Typography>
        ) : (
          bindings.map((b) => (
            <Chip
              key={b.id || `${b.data_table}-${b.data_field}`}
              size="small"
              variant="outlined"
              label={b.field_name ? `${b.table_name} · ${b.field_name}` : b.table_name}
            />
          ))
        )}
      </Stack>

      {rule?.archived ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          This rule is archived and read-only. Unarchive by deleting the archive flag in Operations.
        </Alert>
      ) : null}

      <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase', mb: 0.5 }}>
        Schema v1 JSON Definition
      </Typography>
      <RuleJsonEditor
        value={definitionText}
        onChange={setDefinitionText}
        serverErrors={serverErrors}
        tables={tables}
        disabled={saving || rule?.archived}
      />
    </Box>
  );
}

DefinitionTab.propTypes = {
  rule: PropTypes.object,
  onChanged: PropTypes.func,
};

export default DefinitionTab;
