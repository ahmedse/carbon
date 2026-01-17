import { useState, useEffect, useRef } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Tooltip,
  Collapse,
  Divider,
  Chip,
} from '@mui/material';
import {
  Send,
  SmartToy,
  ExpandMore,
  ExpandLess,
  Refresh,
  Delete,
  BugReport,
  Settings,
  ContentPaste,
  StopCircle,
} from '@mui/icons-material';
import ChatMessage from './ChatMessage';
import AIPreferencesDialog from './AIPreferencesDialog';
import * as aiAPI from '../../api/aiCopilot';
import { API_BASE_URL, API_ROUTES } from '../../config';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';

/**
 * AICopilotPanel - VS Code style with grouped conversations
 */
const AICopilotPanel = ({ projectId = null, collapsed = false }) => {
  const navigate = useNavigate();
  const { context } = useAuth();
  
  // State
  const [conversations, setConversations] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [expandedConvos, setExpandedConvos] = useState(new Set());
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugEvents, setDebugEvents] = useState([]);
  
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom (only within chat panel)
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversations]);

  // Load conversation history
  useEffect(() => {
    loadHistory();
  }, [projectId]);

  const loadHistory = async () => {
    try {
      const data = await aiAPI.getChatHistory(projectId);
      // Backend returns array directly, not {messages: [...]}
      const messages = Array.isArray(data) ? data : (data.messages || []);
      groupMessagesIntoConversations(messages);
    } catch (error) {
      console.error('Failed to load history:', error);
      setConversations([]);
    }
  };

  // Group messages into conversations (new conversation when gap > 30 min)
  const groupMessagesIntoConversations = (messages) => {
    if (!messages.length) {
      setConversations([]);
      return;
    }

    const convos = [];
    let currentConvo = {
      id: Date.now(),
      timestamp: new Date(messages[0].created_at),
      messages: [],
      expanded: true,
    };

    messages.forEach((msg, idx) => {
      const msgTime = new Date(msg.created_at);
      
      // Check if new conversation (gap > 30 minutes)
      if (idx > 0) {
        const prevTime = new Date(messages[idx - 1].created_at);
        const gap = (msgTime - prevTime) / 1000 / 60; // minutes
        
        if (gap > 30) {
          convos.push(currentConvo);
          currentConvo = {
            id: msgTime.getTime(),
            timestamp: msgTime,
            messages: [],
            expanded: false,
          };
        }
      }
      
      currentConvo.messages.push({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: msgTime,
        metadata: msg.metadata || {},
      });
    });

    convos.push(currentConvo);
    
    // Most recent conversation expanded
    if (convos.length > 0) {
      convos[convos.length - 1].expanded = true;
      setExpandedConvos(new Set([convos[convos.length - 1].id]));
    }
    
    setConversations(convos.reverse());
  };

  // Send message
  const handleSendMessage = async (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    const content = inputValue.trim();
    if (!content || loading) return;

    setInputValue('');
    setLoading(true);
    setStreaming(true);

    // Create new conversation if none exist or add to current
    const newMessage = {
      id: Date.now(),
      role: 'user',
      content,
      timestamp: new Date(),
      metadata: {},
    };

    const assistantMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      metadata: { streaming: true },
    };

    // Add to current conversation or create new one
    setConversations(prev => {
      if (prev.length === 0 || !prev[0].expanded) {
        // Create new conversation
        return [{
          id: Date.now(),
          timestamp: new Date(),
          messages: [newMessage, assistantMessage],
          expanded: true,
        }, ...prev];
      } else {
        // Add to current conversation
        const updated = [...prev];
        updated[0] = {
          ...updated[0],
          messages: [...updated[0].messages, newMessage, assistantMessage],
        };
        return updated;
      }
    });

    try {
      setDebugEvents(prev => [
        ...prev,
        { type: 'request', time: new Date(), payload: { message: content, project_id: projectId } },
      ]);

      const token = localStorage.getItem('access');
      const base = API_BASE_URL.replace(/\/+$/, '');
      const path = API_ROUTES.aiChat.replace(/^\/+/, '');
      const url = `${base}/${path}`;

      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: content,
          project_id: projectId,
          stream: true,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Stream error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) throw new Error('Streaming not supported');

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data: '));
          if (!line) continue;
          const payload = line.replace('data: ', '').trim();
          if (!payload) continue;

          let data;
          try {
            data = JSON.parse(payload);
          } catch (e) {
            continue;
          }

          if (data.chunk) {
            setConversations(prev => {
              const updated = [...prev];
              const currentConvo = updated[0];
              const lastMsg = currentConvo.messages[currentConvo.messages.length - 1];
              if (lastMsg.role === 'assistant') {
                lastMsg.content += data.chunk;
              }
              return updated;
            });
          }

          if (data.done) {
            setConversations(prev => {
              const updated = [...prev];
              const currentConvo = updated[0];
              const lastMsg = currentConvo.messages[currentConvo.messages.length - 1];
              if (lastMsg.role === 'assistant') {
                lastMsg.metadata = {
                  ...lastMsg.metadata,
                  streaming: false,
                  tokens_used: data.tokens_used,
                  cost_estimate: data.cost_estimate,
                  sources: data.sources,
                  debug: data.debug || null,
                };
              }
              return updated;
            });

            setDebugEvents(prev => [
              ...prev,
              { type: 'response', time: new Date(), payload: data },
            ]);
          }

          if (data.error) {
            setConversations(prev => {
              const updated = [...prev];
              const currentConvo = updated[0];
              const lastMsg = currentConvo.messages[currentConvo.messages.length - 1];
              if (lastMsg.role === 'assistant') {
                lastMsg.content = `Error: ${data.error}`;
                lastMsg.metadata.streaming = false;
                lastMsg.metadata.error = true;
              }
              return updated;
            });
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Chat error:', error);
        setConversations(prev => {
          const updated = [...prev];
          const currentConvo = updated[0];
          const lastMsg = currentConvo.messages[currentConvo.messages.length - 1];
          if (lastMsg.role === 'assistant') {
            lastMsg.content = 'Failed to get response. Please try again.';
            lastMsg.metadata.streaming = false;
            lastMsg.metadata.error = true;
          }
          return updated;
        });
      }
    } finally {
      setLoading(false);
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      handleSendMessage();
    }
  };

  const toggleConversation = (convoId) => {
    setExpandedConvos(prev => {
      const newSet = new Set(prev);
      if (newSet.has(convoId)) {
        newSet.delete(convoId);
      } else {
        newSet.add(convoId);
      }
      return newSet;
    });
  };

  const handleClearAll = async () => {
    if (window.confirm('Clear all conversation history?')) {
      try {
        await aiAPI.clearChatHistory();
        setConversations([]);
      } catch (error) {
        console.error('Failed to clear history:', error);
      }
    }
  };

  const handleStopStreaming = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      setLoading(false);
      setStreaming(false);
    }
  };

  const handlePasteToInput = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setInputValue(prev => prev + text);
      inputRef.current?.focus();
    } catch (error) {
      console.error('Failed to paste:', error);
    }
  };

  const handleCopyMessage = (content) => {
    navigator.clipboard.writeText(content);
  };

  const handleDeleteMessage = (messageId) => {
    if (window.confirm('Delete this message?')) {
      setConversations(prev => {
        return prev.map(convo => ({
          ...convo,
          messages: convo.messages.filter(m => m.id !== messageId)
        })).filter(convo => convo.messages.length > 0);
      });
    }
  };

  const handleReact = async (messageId, reaction) => {
    try {
      // Optimistically update UI
      setConversations(prev => {
        return prev.map(convo => ({
          ...convo,
          messages: convo.messages.map(m => {
            if (m.id === messageId) {
              const currentReaction = m.metadata?.reaction;
              const newReaction = currentReaction === reaction ? null : reaction;
              return {
                ...m,
                metadata: { ...m.metadata, reaction: newReaction }
              };
            }
            return m;
          })
        }));
      });
      
      // Send to backend (handle failure gracefully)
      if (reaction) {
        await aiAPI.reactToMessage(messageId, reaction).catch(() => {
          // Silently fail - reaction is cosmetic
        });
      }
    } catch (error) {
      // Silently handle error - reactions are non-critical
    }
  };

  const handleTogglePin = (messageId) => {
    // Pin logic
  };

  const handleToggleSources = (messageId) => {
    // Toggle sources visibility
  };

  const formatConversationTitle = (convo) => {
    const date = convo.timestamp;
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return `Today at ${date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
    } else if (date.toDateString() === yesterday.toDateString()) {
      return `Yesterday at ${date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
  };

  const getConversationPreview = (convo) => {
    const firstUserMsg = convo.messages.find(m => m.role === 'user');
    return firstUserMsg?.content.slice(0, 50) + (firstUserMsg?.content.length > 50 ? '...' : '') || 'Empty conversation';
  };

  if (collapsed) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 2, gap: 2 }}>
        <Tooltip title="AI Copilot" placement="left">
          <SmartToy sx={{ color: 'primary.main' }} />
        </Tooltip>
      </Box>
    );
  }

  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%', 
      overflow: 'hidden',
      isolation: 'isolate',
    }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SmartToy sx={{ color: 'primary.main' }} />
            <Typography variant="h6">AI Copilot</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Debug panel">
              <IconButton size="small" onClick={() => setDebugOpen(v => !v)}>
                <BugReport fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Refresh history">
              <IconButton size="small" onClick={loadHistory}>
                <Refresh fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Clear all">
              <IconButton size="small" onClick={handleClearAll}>
                <Delete fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Settings">
              <IconButton size="small" onClick={() => setPreferencesOpen(true)}>
                <Settings fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Your intelligent carbon management assistant
        </Typography>
      </Box>

      {/* Conversations List */}
      <Box sx={{ 
        flex: 1, 
        minHeight: 0,
        overflowY: 'auto', 
        overflowX: 'hidden',
        overscrollBehavior: 'contain',
      }}>
        {conversations.length === 0 ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', p: 3 }}>
            <SmartToy sx={{ fontSize: 64, color: 'grey.300', mb: 2 }} />
            <Typography variant="body2" color="text.secondary" textAlign="center">
              Start a conversation! Ask me about carbon accounting, emissions data, or sustainability strategies.
            </Typography>
          </Box>
        ) : (
          conversations.map(convo => {
            const isExpanded = expandedConvos.has(convo.id);
            return (
              <Box key={convo.id} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
                {/* Conversation Header */}
                <Box
                  onClick={() => toggleConversation(convo.id)}
                  sx={{
                    p: 1.5,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    bgcolor: isExpanded ? 'action.selected' : 'transparent',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                >
                  <IconButton size="small" sx={{ p: 0 }}>
                    {isExpanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                  </IconButton>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="caption" fontWeight="medium" display="block">
                      {formatConversationTitle(convo)}
                    </Typography>
                    {!isExpanded && (
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {getConversationPreview(convo)}
                      </Typography>
                    )}
                  </Box>
                  <Chip label={convo.messages.length} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />
                </Box>

                {/* Conversation Messages */}
                <Collapse in={isExpanded}>
                  <Box sx={{ px: 1, py: 1 }}>
                    {convo.messages.map(message => (
                      <ChatMessage
                        key={message.id}
                        message={message}
                        onCopy={handleCopyMessage}
                        onReact={handleReact}
                        onTogglePin={handleTogglePin}
                        onToggleSources={handleToggleSources}
                        onDelete={handleDeleteMessage}
                      />
                    ))}
                  </Box>
                </Collapse>
              </Box>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input Area */}
      <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Box sx={{ display: 'flex', gap: 0.5, mb: 1, alignItems: 'center' }}>
          <Tooltip title="Paste from clipboard">
            <IconButton size="small" onClick={handlePasteToInput}>
              <ContentPaste fontSize="small" />
            </IconButton>
          </Tooltip>
          {streaming && (
            <Tooltip title="Stop streaming">
              <IconButton size="small" onClick={handleStopStreaming} color="error">
                <StopCircle fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {streaming && (
            <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
              AI is responding...
            </Typography>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            size="small"
            multiline
            maxRows={4}
            placeholder="Ask me about your project, emissions data, modules, or data quality..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading}
            inputRef={inputRef}
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: 'background.paper',
              }
            }}
          />
          <IconButton
            color="primary"
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || loading}
            sx={{ alignSelf: 'flex-end' }}
          >
            <Send />
          </IconButton>
        </Box>
      </Box>

      {/* Debug Panel - Below Input */}
      {debugOpen && (
        <Box sx={{
          borderTop: '1px solid',
          borderColor: 'divider',
          bgcolor: 'grey.50',
          p: 1,
          maxHeight: 120,
          overflowY: 'auto',
          flexShrink: 0,
          fontSize: '0.75rem',
        }}>
          <Typography variant="caption" fontWeight="bold" display="block" mb={0.5}>
            Debug Feed (AI + QA)
          </Typography>
          {debugEvents.slice(-5).map((evt, i) => (
            <Typography key={i} variant="caption" display="block" sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
              {evt.type.toUpperCase()} • {evt.time.toLocaleTimeString()}: {JSON.stringify(evt.payload).slice(0, 80)}...
            </Typography>
          ))}
        </Box>
      )}

      {/* Preferences Dialog */}
      <AIPreferencesDialog
        open={preferencesOpen}
        onClose={() => setPreferencesOpen(false)}
      />
    </Box>
  );
};

export default AICopilotPanel;
