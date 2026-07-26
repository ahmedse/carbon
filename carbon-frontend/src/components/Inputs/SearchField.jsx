import React from 'react';
import PropTypes from 'prop-types';
import { TextField, InputAdornment } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

function SearchField({ value, onChange, placeholder, onClear, disabled }) {
  return (
    <TextField
      fullWidth
      size="small"
      variant="outlined"
      placeholder={placeholder}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon fontSize="small" />
          </InputAdornment>
        ),
      }}
    />
  );
}

SearchField.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  onClear: PropTypes.func,
  disabled: PropTypes.bool,
};

SearchField.defaultProps = {
  value: '',
  placeholder: 'Search…',
  onClear: undefined,
  disabled: false,
};

export default React.memo(SearchField);
