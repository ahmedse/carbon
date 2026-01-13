import { Box, Avatar, Paper, Typography } from '@mui/material';
import { SmartToy, Person } from '@mui/icons-material';
import { formatDistanceToNow } from '../../utils/dateUtils';

/**
 * ChatMessage Component
 * Displays a single chat message from user or AI
 */
const ChatMessage = ({ message }) => {
  const isAI = message.role === 'assistant';
  
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        mb: 2,
        flexDirection: isAI ? 'row' : 'row-reverse',
      }}
    >
      <Avatar
        sx={{
          bgcolor: isAI ? 'primary.main' : 'secondary.main',
          width: 32,
          height: 32,
        }}
      >
        {isAI ? <SmartToy fontSize="small" /> : <Person fontSize="small" />}
      </Avatar>
      
      <Box sx={{ flex: 1, maxWidth: '85%' }}>
        <Paper
          elevation={1}
          sx={{
            p: 1.5,
            bgcolor: isAI ? 'background.paper' : 'primary.light',
            color: isAI ? 'text.primary' : 'primary.contrastText',
            borderRadius: 2,
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {message.content}
          </Typography>
        </Paper>
        
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            display: 'block',
            mt: 0.5,
            ml: isAI ? 0 : 'auto',
            textAlign: isAI ? 'left' : 'right',
          }}
        >
          {formatDistanceToNow(message.timestamp)}
        </Typography>
      </Box>
    </Box>
  );
};

export default ChatMessage;
