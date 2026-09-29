import React from 'react';
import UploadIcon from '@mui/icons-material/Upload';
import InboundStudio from '../../components/inbound/InboundStudio';
import { PEOPLE_FIELD_ALIASES } from './inboundAliases';

export default function ImportStudioPage() {
  return (
    <InboundStudio
      kind="typed_object"
      listPath="/people/import"
      ns="people"
      aliases={PEOPLE_FIELD_ALIASES}
      icon={UploadIcon}
    />
  );
}
