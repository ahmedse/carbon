import React, { useCallback } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { useDropzone } from 'react-dropzone';

/**
 * Compact CSV drop zone — the shared inbound upload primitive.
 * Server parse stays the source of truth; this only hands a File up.
 */
function CsvDropzone({
  onFile,
  disabled = false,
  filename = '',
  emptyLabel = 'Drop a CSV or choose a file',
  chooseLabel = 'Choose CSV',
  hint = '',
}) {
  const onDrop = useCallback((accepted) => {
    const file = accepted?.[0];
    if (file && onFile) onFile(file);
  }, [onFile]);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    disabled,
    multiple: false,
    noClick: true,
    accept: { 'text/csv': ['.csv'], 'application/vnd.ms-excel': ['.csv'] },
  });

  return (
    <Box
      {...getRootProps()}
      role="group"
      aria-label={filename || emptyLabel}
      sx={{
        border: '1px dashed',
        borderColor: isDragActive ? 'primary.main' : 'divider',
        bgcolor: isDragActive ? 'action.hover' : 'background.paper',
        px: 1.5,
        py: 1.25,
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        flexWrap: 'wrap',
      }}
    >
      <input {...getInputProps()} />
      <UploadFileIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }} noWrap>
          {filename || emptyLabel}
        </Typography>
        {hint && (
          <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>{hint}</Typography>
        )}
      </Box>
      <Button size="small" variant="outlined" disabled={disabled} onClick={open}>
        {chooseLabel}
      </Button>
    </Box>
  );
}

CsvDropzone.propTypes = {
  onFile: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  filename: PropTypes.string,
  emptyLabel: PropTypes.string,
  chooseLabel: PropTypes.string,
  hint: PropTypes.string,
};

export default React.memo(CsvDropzone);
