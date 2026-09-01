// src/shell/AIGeneratedBadge.jsx
// Wave D3 — AI output transparency: a quiet token marking AI-authored content.
// NOT a colored banner — a small outlined Chip with theme tokens only
// (RULE_8), text + icon so the meaning never rides on color alone (RULE_23).
import PropTypes from 'prop-types';
import { Chip } from '@mui/material';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';

function AIGeneratedBadge({ label = 'AI' }) {
  return (
    <Chip
      size="small"
      variant="outlined"
      color="default"
      icon={
        <SmartToyOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} aria-hidden="true" />
      }
      label={label}
      aria-label={label}
    />
  );
}

AIGeneratedBadge.propTypes = {
  label: PropTypes.string,
};

export default AIGeneratedBadge;
