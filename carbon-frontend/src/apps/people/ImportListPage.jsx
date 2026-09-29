import React from 'react';
import UploadIcon from '@mui/icons-material/Upload';
import InboundList from '../../components/inbound/InboundList';

export default function ImportListPage() {
  return (
    <InboundList
      kind="typed_object"
      listPath="/people/import"
      ns="people"
      icon={UploadIcon}
    />
  );
}
