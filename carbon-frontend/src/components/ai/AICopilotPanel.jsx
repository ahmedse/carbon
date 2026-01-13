import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Tabs,
  Tab,
  Badge,
  CircularProgress,
  Divider,
  Button,
  Tooltip,
} from '@mui/material';
import {
  Send,
  Delete,
  SmartToy,
  Lightbulb,
  Settings,
} from '@mui/icons-material';
import ChatMessage from './ChatMessage';
import ProactiveInsightCard from './ProactiveInsightCard';
import AIPreferencesDialog from './AIPreferencesDialog';
import * as aiAPI from '../../api/aiCopilot';

/**
 * AICopilotPanel Component
 * Main AI assistant panel with chat, insights, and preferences
 */
const AICopilotPanel = ({ projectId = null, collapsed = false }) => {
  const [activeTab, setActiveTab] = useState(0);
  const [messages, setMessages] = useState([]);
  const [insights, setInsights] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // Load chat history and insights on mount
  useEffect(() => {
    loadChatHistory();
    loadInsights();
  }, [projectId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadChatHistory = async () => {
    try {
      setLoadingHistory(true);
      const response = await aiAPI.getChatHistory(projectId);
      let rawMessages = [];
      if (Array.isArray(response)) {
        rawMessages = response;
      } else if (response && response.messages) {
        rawMessages = response.messages;
      } else if (response && response.data) {
        rawMessages = response.data;
      } else {
        console.warn('loadChatHistory: unexpected response shape', response);
        rawMessages = [];
      }

      const formattedMessages = rawMessages.map(aiAPI.formatMessage);
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadInsights = async () => {
    try {
      const response = await aiAPI.getInsights(false); // Only unacknowledged
      const formattedInsights = response.map(aiAPI.formatInsight);
      setInsights(formattedInsights);
    } catch (error) {
      console.error('Failed to load insights:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      const response = await aiAPI.sendMessage(userMessage.content, projectId);
      
      const aiMessage = {
        id: response.id || Date.now() + 1,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(response.created_at || new Date()),
        metadata: response.metadata || {},
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Clear all chat history?')) return;

    try {
      await aiAPI.clearChatHistory(projectId);
      setMessages([]);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  const handleAcknowledgeInsight = async (insightId) => {
    try {
      await aiAPI.acknowledgeInsight(insightId);
      setInsights((prev) => prev.filter((i) => i.id !== insightId));
    } catch (error) {
      console.error('Failed to acknowledge insight:', error);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (collapsed) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 2,
          gap: 2,
        }}
      >
        <IconButton color="primary">
          <SmartToy />
        </IconButton>
        {insights.length > 0 && (
          <Badge badgeContent={insights.length} color="error">
            <Lightbulb />
          </Badge>
        )}
      </Box>
    );
  }

  return (
    <Paper
      elevation={3}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, bgcolor: 'primary.main', color: 'white' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SmartToy />
          <Typography variant="h6" sx={{ flex: 1 }}>Carbon AI Copilot</Typography>
          <Tooltip title="Preferences">
            <IconButton
              size="small"
              onClick={() => setPreferencesOpen(true)}
              sx={{ color: 'white' }}
            >
              <Settings fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Typography variant="caption">
          Your intelligent carbon management assistant
        </Typography>
      </Box>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onChange={(e, newValue) => setActiveTab(newValue)}
        sx={{ borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Chat" icon={<SmartToy />} iconPosition="start" />
        <Tab
          label="Insights"
          icon={
            <Badge badgeContent={insights.length} color="error">
              <Lightbulb />
            </Badge>
          }
          iconPosition="start"
        />
      </Tabs>

      {/* Tab Content */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {/* Chat Tab */}
        {activeTab === 0 && (
          <>
            {/* Messages Area */}
            <Box
              sx={{
                flex: 1,
                overflowY: 'auto',
                p: 2,
                bgcolor: 'grey.50',
              }}
            >
              {loadingHistory ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress />
                </Box>
              ) : messages.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <SmartToy sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                  <Typography variant="body2" color="text.secondary">
                    Start a conversation! Ask me about carbon accounting,
                    GHG protocols, or your emissions data.
                  </Typography>
                </Box>
              ) : (
                messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))
              )}
              
              {loading && (
                <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
                  <CircularProgress size={32} />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    AI is thinking...
                  </Typography>
                </Box>
              )}
              
              <div ref={messagesEndRef} />
            </Box>

            <Divider />

            {/* Input Area */}
            <Box sx={{ p: 2, bgcolor: 'background.paper' }}>
              {messages.length > 0 && (
                <Button
                  size="small"
                  startIcon={<Delete />}
                  onClick={handleClearHistory}
                  sx={{ mb: 1 }}
                >
                  Clear History
                </Button>
              )}
              
              <Box sx={{ display: 'flex', gap: 1 }}>
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  maxRows={4}
                  placeholder="Ask me anything about carbon management..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  disabled={loading}
                />
                <IconButton
                  color="primary"
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || loading}
                >
                  <Send />
                </IconButton>
              </Box>
            </Box>
          </>
        )}

        {/* Insights Tab */}
        {activeTab === 1 && (
          <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
            {insights.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Lightbulb sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                <Typography variant="body2" color="text.secondary">
                  No new insights at the moment.
                  <br />
                  I'll notify you when I find something important!
                </Typography>
              </Box>
            ) : (
              insights.map((insight) => (
                <ProactiveInsightCard
                  key={insight.id}
                  insight={insight}
                  onAcknowledge={handleAcknowledgeInsight}
                />
              ))
            )}
          </Box>
        )}
      </Box>

      {/* Preferences Dialog */}
      <AIPreferencesDialog
        open={preferencesOpen}
        onClose={() => setPreferencesOpen(false)}
      />
    </Paper>
  );
};

export default AICopilotPanel;
