import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Box,
  Chip,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  Lightbulb,
  Warning,
  Info,
  Error as ErrorIcon,
  Close,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

/**
 * ProactiveInsightCard Component
 * Displays AI-generated insights with urgency levels
 */
const ProactiveInsightCard = ({ insight, onAcknowledge }) => {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  const getUrgencyConfig = (urgency) => {
    switch (urgency) {
      case 'critical':
        return { color: 'error', icon: <ErrorIcon />, label: 'Critical' };
      case 'high':
        return { color: 'warning', icon: <Warning />, label: 'High Priority' };
      case 'medium':
        return { color: 'info', icon: <Info />, label: 'Medium' };
      default:
        return { color: 'default', icon: <Lightbulb />, label: 'Low' };
    }
  };

  const urgencyConfig = getUrgencyConfig(insight.urgency);

  const handleAction = () => {
    if (insight.actionUrl) {
      navigate(insight.actionUrl);
    }
  };

  const handleAcknowledge = () => {
    if (onAcknowledge) {
      onAcknowledge(insight.id);
    }
  };

  return (
    <Card
      elevation={2}
      sx={{
        mb: 2,
        borderLeft: 4,
        borderColor: `${urgencyConfig.color}.main`,
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          <Box sx={{ color: `${urgencyConfig.color}.main`, mt: 0.5 }}>
            {urgencyConfig.icon}
          </Box>

          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2" sx={{ flex: 1 }}>
                {insight.title}
              </Typography>
              <Chip
                label={urgencyConfig.label}
                size="small"
                color={urgencyConfig.color}
              />
              <IconButton size="small" onClick={handleAcknowledge}>
                <Close fontSize="small" />
              </IconButton>
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {expanded
                ? insight.description
                : `${insight.description.substring(0, 100)}${
                    insight.description.length > 100 ? '...' : ''
                  }`}
            </Typography>

            {insight.description.length > 100 && (
              <Button
                size="small"
                onClick={() => setExpanded(!expanded)}
                endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
                sx={{ mb: 1 }}
              >
                {expanded ? 'Show Less' : 'Show More'}
              </Button>
            )}

            {insight.actionLabel && (
              <Button
                variant="contained"
                size="small"
                onClick={handleAction}
                sx={{ mt: 1 }}
              >
                {insight.actionLabel}
              </Button>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ProactiveInsightCard;
