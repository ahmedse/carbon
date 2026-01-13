import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  FormControlLabel,
  FormLabel,
  Switch,
  RadioGroup,
  Radio,
  Box,
  Typography,
  Divider,
} from '@mui/material';
import * as aiAPI from '../../api/aiCopilot';

/**
 * AIPreferencesDialog Component
 * Allows users to customize AI behavior and notifications
 */
const AIPreferencesDialog = ({ open, onClose }) => {
  const [preferences, setPreferences] = useState({
    enable_proactive_insights: true,
    response_detail_level: 'balanced',
    allow_conversation_learning: true,
  });
  
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      loadPreferences();
    }
  }, [open]);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const data = await aiAPI.getPreferences();
      setPreferences({
        enable_proactive_insights: data.enable_proactive_insights,
        response_detail_level: data.response_detail_level,
        allow_conversation_learning: data.allow_conversation_learning,
      });
    } catch (error) {
      console.error('Failed to load preferences:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await aiAPI.updatePreferences(preferences);
      onClose();
    } catch (error) {
      console.error('Failed to save preferences:', error);
      alert('Failed to save preferences. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setPreferences((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>AI Copilot Preferences</DialogTitle>
      
      <DialogContent>
        {loading ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography>Loading preferences...</Typography>
          </Box>
        ) : (
          <Box sx={{ pt: 2 }}>
            {/* Proactive Insights */}
            <FormControl component="fieldset" fullWidth sx={{ mb: 3 }}>
              <FormLabel component="legend">Proactive Insights</FormLabel>
              <FormControlLabel
                control={
                  <Switch
                    checked={preferences.enable_proactive_insights}
                    onChange={(e) =>
                      handleChange('enable_proactive_insights', e.target.checked)
                    }
                  />
                }
                label="Enable proactive insights and notifications"
              />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 4, mt: 0.5 }}>
                AI will proactively suggest improvements and alert you to potential issues
              </Typography>
            </FormControl>

            <Divider sx={{ my: 2 }} />

            {/* Response Detail Level */}
            <FormControl component="fieldset" fullWidth sx={{ mb: 3 }}>
              <FormLabel component="legend">Response Detail Level</FormLabel>
              <RadioGroup
                value={preferences.response_detail_level}
                onChange={(e) => handleChange('response_detail_level', e.target.value)}
              >
                <FormControlLabel
                  value="concise"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body2">Concise</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Short, direct answers
                      </Typography>
                    </Box>
                  }
                />
                <FormControlLabel
                  value="balanced"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body2">Balanced (Recommended)</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Clear explanations with helpful context
                      </Typography>
                    </Box>
                  }
                />
                <FormControlLabel
                  value="detailed"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body2">Detailed</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Comprehensive answers with examples
                      </Typography>
                    </Box>
                  }
                />
              </RadioGroup>
            </FormControl>

            <Divider sx={{ my: 2 }} />

            {/* Conversation Learning */}
            <FormControl component="fieldset" fullWidth>
              <FormLabel component="legend">Privacy & Learning</FormLabel>
              <FormControlLabel
                control={
                  <Switch
                    checked={preferences.allow_conversation_learning}
                    onChange={(e) =>
                      handleChange('allow_conversation_learning', e.target.checked)
                    }
                  />
                }
                label="Allow AI to learn from my conversations"
              />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 4, mt: 0.5 }}>
                Helps improve AI responses for you and your team (conversations remain private)
              </Typography>
            </FormControl>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={loading || saving}
        >
          {saving ? 'Saving...' : 'Save Preferences'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AIPreferencesDialog;
