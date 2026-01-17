import { Box, Avatar, Paper, Typography, IconButton, Tooltip } from '@mui/material';
import { SmartToy, Person, ContentCopy, ThumbUp, ThumbDown, PushPin, MenuBook, Delete } from '@mui/icons-material';
import { formatDistanceToNow } from '../../utils/dateUtils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * ChatMessage Component
 * Displays a single chat message from user or AI
 */
const ChatMessage = ({ message, onCopy, onReact, onTogglePin, onToggleSources, onDelete, containerRef, isMatch }) => {
  const isAI = message.role === 'assistant';
  const sources = message.metadata?.sources || [];
  const showSources = message.metadata?.showSources;
  const reaction = message.metadata?.reaction;
  const pinned = message.metadata?.pinned;
  
  return (
    <Box
      ref={containerRef}
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
            position: 'relative',
            border: isMatch ? '1px solid' : 'none',
            borderColor: isMatch ? 'primary.light' : 'transparent',
          }}
        >
          <Tooltip title="Copy message">
            <IconButton
              size="small"
              onClick={() => onCopy?.(message.content)}
              sx={{
                position: 'absolute',
                top: 4,
                right: 4,
                width: 22,
                height: 22,
                color: isAI ? 'text.secondary' : 'primary.contrastText',
                bgcolor: isAI ? 'grey.100' : 'rgba(255,255,255,0.15)',
                '&:hover': { bgcolor: isAI ? 'grey.200' : 'rgba(255,255,255,0.25)' },
              }}
            >
              <ContentCopy sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          {isAI ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <Typography variant="body2" sx={{ mb: 1, pr: 3 }}>{children}</Typography>,
                h1: ({ children }) => <Typography variant="h6" sx={{ fontWeight: 'bold', mt: 1, mb: 0.5, pr: 3 }}>{children}</Typography>,
                h2: ({ children }) => <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mt: 1, mb: 0.5, pr: 3 }}>{children}</Typography>,
                h3: ({ children }) => <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mt: 0.5, mb: 0.5, pr: 3 }}>{children}</Typography>,
                ul: ({ children }) => <Box component="ul" sx={{ pl: 2, my: 0.5, pr: 3 }}>{children}</Box>,
                ol: ({ children }) => <Box component="ol" sx={{ pl: 2, my: 0.5, pr: 3 }}>{children}</Box>,
                li: ({ children }) => <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>{children}</Typography>,
                code: ({ inline, children }) => (
                  inline ? (
                    <Box
                      component="code"
                      sx={{
                        bgcolor: 'grey.200',
                        color: 'error.main',
                        px: 0.5,
                        py: 0.2,
                        borderRadius: 0.5,
                        fontSize: '0.875em',
                        fontFamily: 'monospace',
                      }}
                    >
                      {children}
                    </Box>
                  ) : (
                    <Box
                      component="pre"
                      sx={{
                        bgcolor: 'grey.100',
                        p: 1.5,
                        borderRadius: 1,
                        overflow: 'auto',
                        mr: 3,
                        my: 1,
                      }}
                    >
                      <Box
                        component="code"
                        sx={{
                          fontSize: '0.875em',
                          fontFamily: 'monospace',
                        }}
                      >
                        {children}
                      </Box>
                    </Box>
                  )
                ),
                blockquote: ({ children }) => (
                  <Box
                    sx={{
                      borderLeft: '4px solid',
                      borderColor: 'primary.main',
                      pl: 2,
                      py: 0.5,
                      my: 1,
                      fontStyle: 'italic',
                      bgcolor: 'grey.50',
                      mr: 3,
                    }}
                  >
                    {children}
                  </Box>
                ),
                strong: ({ children }) => <Box component="strong" sx={{ fontWeight: 'bold' }}>{children}</Box>,
                em: ({ children }) => <Box component="em" sx={{ fontStyle: 'italic' }}>{children}</Box>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', pr: 3 }}>
              {message.content}
            </Typography>
          )}
        </Paper>

        {isAI && (
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            <Tooltip title="Thumbs up">
              <IconButton
                size="small"
                onClick={() => onReact?.(message.id, reaction === 'up' ? null : 'up')}
                sx={{ color: reaction === 'up' ? 'primary.main' : 'text.secondary' }}
              >
                <ThumbUp sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Thumbs down">
              <IconButton
                size="small"
                onClick={() => onReact?.(message.id, reaction === 'down' ? null : 'down')}
                sx={{ color: reaction === 'down' ? 'error.main' : 'text.secondary' }}
              >
                <ThumbDown sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={pinned ? 'Unpin message' : 'Pin message'}>
              <IconButton
                size="small"
                onClick={() => onTogglePin?.(message.id)}
                sx={{ color: pinned ? 'warning.main' : 'text.secondary' }}
              >
                <PushPin sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            {sources.length > 0 && (
              <Tooltip title={showSources ? 'Hide citations' : 'Show citations'}>
                <IconButton
                  size="small"
                  onClick={() => onToggleSources?.(message.id)}
                  sx={{ color: showSources ? 'primary.main' : 'text.secondary' }}
                >
                  <MenuBook sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Delete message">
              <IconButton
                size="small"
                onClick={() => onDelete?.(message.id)}
                sx={{ color: 'text.secondary', '&:hover': { color: 'error.main' } }}
              >
                <Delete sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {!isAI && (
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, justifyContent: 'flex-end' }}>
            <Tooltip title="Delete message">
              <IconButton
                size="small"
                onClick={() => onDelete?.(message.id)}
                sx={{ color: 'primary.contrastText', opacity: 0.7, '&:hover': { opacity: 1, color: 'error.main' } }}
              >
                <Delete sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {isAI && showSources && sources.length > 0 && (
          <Box sx={{ mt: 1, p: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Citations
            </Typography>
            {sources.map((s, i) => (
              <Box key={`${s.source}-${i}`} sx={{ mb: 0.75 }}>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {s.source}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {s.snippet}
                </Typography>
              </Box>
            ))}
          </Box>
        )}
        
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
