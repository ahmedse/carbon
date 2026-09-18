// src/pages/catalog/tabs/AssetEditTab.jsx
// Asset Edit Tab: Governance form for updating asset profile metadata

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, TextField, Button, CircularProgress, Alert, 
  Chip, Typography
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { apiFetch } from '../../../api/api';


export default function AssetEditTab({ entityData, additionalProps = {} }) {
  const { t } = useTranslation('catalog');
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
      label: d.name || d.title || t('unknown')
    }));
  }, [selectOptions.domains, t]);

  // Build user options (support both array and object with id/username)
  const userOptions = useMemo(() => {
    const users = selectOptions.users || [];
    if (!Array.isArray(users)) return [];
    return users.map(u => ({
      id: u.id,
      label: u.username || u.email || u.first_name || t('unknown')
    }));
  }, [selectOptions.users, t]);

  // Build glossary term options
  const glossaryOptions = useMemo(() => {
    const terms = selectOptions.glossaryTerms || [];
    if (!Array.isArray(terms)) return [];
    return terms.map(term => ({
      id: term.id,
      label: term.name || term.term || t('unknown')
    }));
  }, [selectOptions.glossaryTerms, t]);

  // Build tag options
  const _tagOptions = useMemo(() => {
    const tags = selectOptions.tags || [];
    if (!Array.isArray(tags)) return [];
    return tags.map(tag => ({
      id: tag.id,
      label: tag.name || t('unknown')
    }));
  }, [selectOptions.tags, t]);

  const handleChange = (e) => {
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
      setError(t('titleRequired'));
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

      notify({ message: t('assetUpdated'), type: 'success' });
      
      // Call parent callback to refresh data
      if (onAssetUpdated) {
        onAssetUpdated();
      }
    } catch (err) {
      const message = err.message || t('failedToSaveAsset');
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

        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>{t('basicInformation')}</Typography>

        <TextField
          fullWidth
          label={t('title')}
          name="title"
          value={formData.title}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          required
        />

        <TextField
          fullWidth
          label={t('description')}
          name="description"
          value={formData.description}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          multiline
          rows={3}
        />

        <Typography variant="subtitle2" sx={{ mb: 2, mt: 3, fontWeight: 600 }}>{t('governance')}</Typography>

        <Box sx={{ mt: 2 }}>
          <SearchSelect
            options={domainOptions}
            valueKey="id"
            labelKey="label"
            label={t('domain')}
            helperText={t('domainSelectHelper')}
            value={formData.domain}
            onChange={(v) => setFormData((prev) => ({ ...prev, domain: v?.id ?? '' }))}
            noOptionsText={t('noDomains') || 'No domains'}
          />
        </Box>

        <Box sx={{ mt: 2 }}>
          <SearchSelect
            options={classificationOptions}
            valueKey="value"
            labelKey="label"
            label={t('classification')}
            helperText={t('classificationHelper')}
            value={formData.classification}
            onChange={(v) => setFormData((prev) => ({ ...prev, classification: v?.value ?? 'internal' }))}
            clearable={false}
          />
        </Box>

        <Box sx={{ mt: 2 }}>
          <SearchSelect
            options={userOptions}
            valueKey="id"
            labelKey="label"
            label={t('owner')}
            helperText={t('ownerBusinessHelper')}
            value={formData.owner}
            onChange={(v) => setFormData((prev) => ({ ...prev, owner: v?.id ?? '' }))}
            noOptionsText={t('noUsers') || 'No users'}
          />
        </Box>

        <Box sx={{ mt: 2 }}>
          <SearchSelect
            options={userOptions}
            valueKey="id"
            labelKey="label"
            label={t('steward')}
            helperText={t('stewardGovernanceHelper')}
            value={formData.steward}
            onChange={(v) => setFormData((prev) => ({ ...prev, steward: v?.id ?? '' }))}
            noOptionsText={t('noUsers') || 'No users'}
          />
        </Box>

        <Typography variant="subtitle2" sx={{ mb: 2, mt: 3, fontWeight: 600 }}>{t('semanticAndClassification')}</Typography>

        <TextField
          fullWidth
          label={t('semanticType')}
          name="semantic_type"
          value={formData.semantic_type}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          placeholder={t('semanticTypePlaceholder')}
          helperText={t('entityTypeHelper')}
        />

        <Box sx={{ mt: 2 }}>
          <SearchSelect
            options={glossaryOptions}
            valueKey="id"
            labelKey="label"
            label={t('glossaryTerm')}
            helperText={t('glossaryTermLinkHelper')}
            value={formData.glossary_term}
            onChange={(v) => setFormData((prev) => ({ ...prev, glossary_term: v?.id ?? '' }))}
            noOptionsText={t('noGlossaryTerms') || 'No glossary terms'}
          />
        </Box>

        <Box sx={{ mt: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>{t('tags')}</Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <TextField
              size="small"
              placeholder={t('enterTagPlaceholder')}
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
              {t('add')}
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
            {saving ? <CircularProgress size={24} /> : t('saveChanges')}
          </Button>
        </Box>
      </Box>
    </DetailTabContent>
  );
}
