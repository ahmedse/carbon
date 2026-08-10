// src/pages/catalog/tabs/AssetEditTab.jsx
// Asset Edit Tab: Governance form for updating asset profile metadata

import React, { useState, useMemo } from 'react';
import { 
  Box, TextField, Button, CircularProgress, Alert, 
  MenuItem, Chip, FormControl, InputLabel, Select,
  FormHelperText, Typography
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { apiFetch } from '../../../api/api';


export default function AssetEditTab({ entityData, additionalProps = {} }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { selectOptions = {}, onAssetUpdated = null } = additionalProps;

  const [formData, setFormData] = useState({
    title: entityData?.title || '',
    description: entityData?.description || '',
    domain: entityData?.domain || '',
    classification: entityData?.classification || 'internal',
    owner: entityData?.owner || '',
    steward: entityData?.steward || '',
    semantic_type: entityData?.semantic_type || '',
    glossary_term: entityData?.glossary_term || '',
    tags: entityData?.tags || [],
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [tagInput, setTagInput] = useState('');

  const classificationOptions = [
    { value: 'public', label: 'Public' },
    { value: 'internal', label: 'Internal' },
    { value: 'confidential', label: 'Confidential' },
    { value: 'pii', label: 'PII (Personally Identifiable Info)' },
    { value: 'sensitive', label: 'Sensitive' },
  ];

  // Build domain options (support both array and object with id/name)
  const domainOptions = useMemo(() => {
    const domains = selectOptions.domains || [];
    if (!Array.isArray(domains)) return [];
    return domains.map(d => ({
      id: d.id,
      label: d.name || d.title || 'Unknown'
    }));
  }, [selectOptions.domains]);

  // Build user options (support both array and object with id/username)
  const userOptions = useMemo(() => {
    const users = selectOptions.users || [];
    if (!Array.isArray(users)) return [];
    return users.map(u => ({
      id: u.id,
      label: u.username || u.email || u.first_name || 'Unknown'
    }));
  }, [selectOptions.users]);

  // Build glossary term options
  const glossaryOptions = useMemo(() => {
    const terms = selectOptions.glossaryTerms || [];
    if (!Array.isArray(terms)) return [];
    return terms.map(t => ({
      id: t.id,
      label: t.name || t.term || 'Unknown'
    }));
  }, [selectOptions.glossaryTerms]);

  // Build tag options
  const _tagOptions = useMemo(() => {
    const tags = selectOptions.tags || [];
    if (!Array.isArray(tags)) return [];
    return tags.map(t => ({
      id: t.id,
      label: t.name || 'Unknown'
    }));
  }, [selectOptions.tags]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSelectChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, tagInput.trim()]
      }));
      setTagInput('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(t => t !== tagToRemove)
    }));
  };

  const handleSave = async () => {
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      // Prepare payload with only the fields we're updating
      const payload = {
        title: formData.title,
        description: formData.description,
        domain: formData.domain || null,
        classification: formData.classification,
        owner: formData.owner || null,
        steward: formData.steward || null,
        semantic_type: formData.semantic_type || null,
        glossary_term: formData.glossary_term || null,
        tags: formData.tags,
      };

      const updatedAsset = await apiFetch(`catalog/assets/${entityData.id}/`, {
        method: 'PATCH',
        token,
        body: payload,
      }); // update asset

      setFormData({
        title: updatedAsset.title || '',
        description: updatedAsset.description || '',
        domain: updatedAsset.domain || '',
        classification: updatedAsset.classification || 'internal',
        owner: updatedAsset.owner || '',
        steward: updatedAsset.steward || '',
        semantic_type: updatedAsset.semantic_type || '',
        glossary_term: updatedAsset.glossary_term || '',
        tags: updatedAsset.tags || [],
      });

      notify({ message: 'Asset updated successfully', type: 'success' });
      
      // Call parent callback to refresh data
      if (onAssetUpdated) {
        onAssetUpdated();
      }
    } catch (err) {
      const message = err.message || 'Failed to save asset';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: '800px' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>Basic Information</Typography>

        <TextField
          fullWidth
          label="Title"
          name="title"
          value={formData.title}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          required
        />

        <TextField
          fullWidth
          label="Description"
          name="description"
          value={formData.description}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          multiline
          rows={3}
        />

        <Typography variant="subtitle2" sx={{ mb: 2, mt: 3, fontWeight: 600 }}>Governance</Typography>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Domain</InputLabel>
          <Select
            name="domain"
            value={formData.domain}
            onChange={handleSelectChange}
            label="Domain"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {domainOptions.map((domain) => (
              <MenuItem key={domain.id} value={domain.id}>
                {domain.label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Select the data domain this asset belongs to</FormHelperText>
        </FormControl>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Classification</InputLabel>
          <Select
            name="classification"
            value={formData.classification}
            onChange={handleSelectChange}
            label="Classification"
          >
            {classificationOptions.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Security/sensitivity classification level</FormHelperText>
        </FormControl>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Owner</InputLabel>
          <Select
            name="owner"
            value={formData.owner}
            onChange={handleSelectChange}
            label="Owner"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Business owner responsible for this asset</FormHelperText>
        </FormControl>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Steward</InputLabel>
          <Select
            name="steward"
            value={formData.steward}
            onChange={handleSelectChange}
            label="Steward"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Data steward responsible for governance</FormHelperText>
        </FormControl>

        <Typography variant="subtitle2" sx={{ mb: 2, mt: 3, fontWeight: 600 }}>Semantic & Classification</Typography>

        <TextField
          fullWidth
          label="Semantic Type"
          name="semantic_type"
          value={formData.semantic_type}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          placeholder="e.g., Customer, Transaction, Product"
          helperText="Entity type or semantic concept"
        />

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Glossary Term</InputLabel>
          <Select
            name="glossary_term"
            value={formData.glossary_term}
            onChange={handleSelectChange}
            label="Glossary Term"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {glossaryOptions.map((term) => (
              <MenuItem key={term.id} value={term.id}>
                {term.label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Link to standard business glossary term</FormHelperText>
        </FormControl>

        <Box sx={{ mt: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Tags</Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <TextField
              size="small"
              placeholder="Enter a tag"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddTag();
                }
              }}
              sx={{ flex: 1 }}
            />
            <Button
              variant="outlined"
              onClick={handleAddTag}
              disabled={!tagInput.trim()}
            >
              Add
            </Button>
          </Box>
          {formData.tags.length > 0 && (
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {formData.tags.map((tag, idx) => (
                <Chip
                  key={idx}
                  label={tag}
                  onDelete={() => handleRemoveTag(tag)}
                  variant="outlined"
                />
              ))}
            </Box>
          )}
        </Box>

        <Box sx={{ mt: 3, display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </DetailTabContent>
  );
}
