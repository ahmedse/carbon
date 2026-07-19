// File: src/pages/dataschema/tabs/RowEvidenceTab.jsx
// Evidence tab - file upload and viewer (reuses existing components)

import React from 'react';
import { Box } from '@mui/material';
import EvidenceUploader from '../../../components/evidence/EvidenceUploader';
import EvidenceViewer from '../../../components/evidence/EvidenceViewer';

export default function RowEvidenceTab({ rowId, token }) {
  const handleUploadComplete = () => {
    // Trigger refresh of evidence viewer
    window.dispatchEvent(
      new CustomEvent('evidenceRefresh', { detail: { rowId } })
    );
  };

  return (
    <Box sx={{ maxWidth: '800px' }}>
      {/* Upload section */}
      <Box sx={{ mb: 3 }}>
        <EvidenceUploader
          dataRowId={rowId}
          token={token}
          onUploadComplete={handleUploadComplete}
        />
      </Box>

      {/* Evidence viewer section */}
      <Box>
        <EvidenceViewer
          dataRowId={rowId}
          token={token}
        />
      </Box>
    </Box>
  );
}
