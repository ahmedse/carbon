import React from 'react';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import InboundList from '../../components/inbound/InboundList';

export default function ImportsDetailPage() {
  return (
    <InboundList
      kind="data_product"
      listPath="/catalog/imports"
      ns="catalog"
      icon={CloudUploadIcon}
    />
  );
}
