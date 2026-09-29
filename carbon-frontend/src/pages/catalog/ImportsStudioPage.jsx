import React from 'react';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import InboundStudio from '../../components/inbound/InboundStudio';

export default function ImportsStudioPage() {
  return (
    <InboundStudio
      kind="data_product"
      listPath="/catalog/imports"
      ns="catalog"
      icon={CloudUploadIcon}
    />
  );
}
