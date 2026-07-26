import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button } from '@mui/material';

function SaveBar({ onSave, onCancel, saving, saveLabel, dirty }) {
  if (!dirty) return null;

  return (
    <Box sx={{ position: 'sticky', bottom: 0, zIndex: 10, bgcolor: 'background.paper', borderTop: '1px solid', borderColor: 'divider', p: 2, display: 'flex', gap: 2, justifyContent: 'space-between' }}>
      <Button variant="outlined" color="inherit" size="small" onClick={onCancel}>
        Cancel
      </Button>
      <Button variant="contained" size="small" color="primary" onClick={onSave} disabled={saving}>
        {saving ? 'Saving…' : saveLabel}
      </Button>
    </Box>
  );
}

SaveBar.propTypes = {
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  saving: PropTypes.bool,
  saveLabel: PropTypes.string,
  dirty: PropTypes.bool,
};

SaveBar.defaultProps = {
  saving: false,
  saveLabel: 'Save Changes',
  dirty: false,
};

export default React.memo(SaveBar);
