import React from 'react';
import PropTypes from 'prop-types';
import { List, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';

function SidebarNav({ items, selectedKey, onSelect }) {
  return (
    <List disablePadding>
      {items.map((item) => (
        <ListItemButton
          key={item.key}
          selected={item.key === selectedKey}
          onClick={() => onSelect(item.key)}
          sx={{ borderRadius: 2, mb: 1 }}
        >
          {item.icon && <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>}
          <ListItemText primary={item.label} secondary={item.subtitle} />
        </ListItemButton>
      ))}
    </List>
  );
}

SidebarNav.propTypes = {
  items: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    subtitle: PropTypes.string,
    icon: PropTypes.element,
  })).isRequired,
  selectedKey: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};

SidebarNav.defaultProps = {
  selectedKey: '',
};

export default React.memo(SidebarNav);
