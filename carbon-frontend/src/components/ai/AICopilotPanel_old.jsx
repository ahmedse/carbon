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
  Tooltip,
  InputAdornment,
} from '@mui/material';
import {
  Send,
  Delete,
  SmartToy,
  Lightbulb,
  Settings,
  Replay,
  StopCircle,
  Restore,
  History,
  Download,
  ContentPaste,
  Search,
  FactCheck,
  WarningAmber,
  KeyboardArrowUp,
  KeyboardArrowDown,
  BugReport,
} from '@mui/icons-material';
import ChatMessage from './ChatMessage';
import ProactiveInsightCard from './ProactiveInsightCard';
import AIPreferencesDialog from './AIPreferencesDialog';
import * as aiAPI from '../../api/aiCopilot';
import { API_BASE_URL, API_ROUTES } from '../../config';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';

/**
 * AICopilotPanel Component
 * Main AI assistant panel with chat, insights, and preferences
 */
const AICopilotPanel = ({ projectId = null, collapsed = false }) => {
  const navigate = useNavigate();
  const { context } = useAuth();
  const [activeTab, setActiveTab] = useState(0);
  const [messages, setMessages] = useState([]);
  const [insights, setInsights] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [clearedMessages, setClearedMessages] = useState([]);
  const [lastUserMessage, setLastUserMessage] = useState('');
  const [filterText, setFilterText] = useState('');
  const [matchIndex, setMatchIndex] = useState(-1);
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugEvents, setDebugEvents] = useState([]);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  const messageRefs = useRef({});

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
      const lastUser = [...formattedMessages].reverse().find((m) => m.role === 'user');
      if (lastUser?.content) setLastUserMessage(lastUser.content);
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

  const handleSendMessage = async (overrideMessage = null) => {
    const content = overrideMessage ?? inputValue.trim();
    if (!content || loading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLastUserMessage(content);
    setLoading(true);
    setStreaming(true);

    const assistantMessageId = Date.now() + 1;
    const assistantMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      metadata: { streaming: true },
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      setDebugEvents((prev) => [
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
          const line = part.split('\n').find((l) => l.startsWith('data: '));
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
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + data.chunk }
                  : m
              )
            );
          }

          if (data.done) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      metadata: {
                        ...m.metadata,
                        streaming: false,
                        tokens_used: data.tokens_used,
                        cost_estimate: data.cost_estimate,
                        sources: data.sources,
                        debug: data.debug || null,
                      },
                    }
                  : m
              )
            );

            if (data.debug) {
              setDebugEvents((prev) => [
                ...prev,
                { type: 'response', time: new Date(), payload: data.debug },
              ]);
            }
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to send message:', error);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? { ...m, content: 'Sorry, I encountered an error. Please try again.' }
              : m
          )
        );
      }
    } finally {
      setLoading(false);
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Clear all chat history?')) return;

    try {
      setClearedMessages(messages);
      await aiAPI.clearChatHistory(projectId);
      setMessages([]);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  const handleRestoreHistory = () => {
    if (clearedMessages.length === 0) return;
    setMessages(clearedMessages);
    setClearedMessages([]);
  };

  const handleRetryLast = () => {
    if (!lastUserMessage || loading) return;
    handleSendMessage(lastUserMessage);
  };

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  };

  const handleExportHistory = () => {
    if (!messages.length) return;
    const exportData = messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      metadata: m.metadata || {},
    }));

    const jsonBlob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const jsonUrl = URL.createObjectURL(jsonBlob);
    const jsonLink = document.createElement('a');
    jsonLink.href = jsonUrl;
    jsonLink.download = 'ai-chat-history.json';
    jsonLink.click();
    URL.revokeObjectURL(jsonUrl);

    const csvHeader = 'id,role,timestamp,content\n';
    const csvRows = exportData
      .map((m) => `${m.id},${m.role},${new Date(m.timestamp).toISOString()},"${String(m.content).replace(/"/g, '""')}"`)
      .join('\n');
    const csvBlob = new Blob([csvHeader + csvRows], { type: 'text/csv' });
    const csvUrl = URL.createObjectURL(csvBlob);
    const csvLink = document.createElement('a');
    csvLink.href = csvUrl;
    csvLink.download = 'ai-chat-history.csv';
    csvLink.click();
    URL.revokeObjectURL(csvUrl);
  };

  const handleCopyMessage = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      console.error('Copy failed:', error);
    }
  };

  const handlePasteToInput = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setInputValue((prev) => (prev ? `${prev}\n${text}` : text));
    } catch (error) {
      console.error('Paste failed:', error);
    }
  };

  const handleReact = async (messageId, reaction) => {
    const nextReaction = reaction;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              metadata: {
                ...m.metadata,
                reaction: m.metadata?.reaction === reaction ? null : reaction,
              },
            }
          : m
      )
    );

    try {
      const finalReaction =
        messages.find((m) => m.id === messageId)?.metadata?.reaction === nextReaction
          ? null
          : nextReaction;
      await aiAPI.reactToMessage(messageId, finalReaction);
    } catch (error) {
      console.error('Failed to persist reaction:', error);
    }
  };

  const handleTogglePin = (messageId) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              metadata: {
                ...m.metadata,
                pinned: !m.metadata?.pinned,
              },
            }
          : m
      )
    );
  };

  const handleToggleSources = (messageId) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              metadata: {
                ...m.metadata,
                showSources: !m.metadata?.showSources,
              },
            }
          : m
      )
    );
  };

  const matchingIds = filterText
    ? messages
        .filter((m) => m.content.toLowerCase().includes(filterText.toLowerCase()))
        .map((m) => m.id)
    : [];

  const jumpToMatch = (index) => {
    if (!matchingIds.length) return;
    const clamped = (index + matchingIds.length) % matchingIds.length;
    setMatchIndex(clamped);
    const id = matchingIds[clamped];
    const el = messageRefs.current[id];
    if (el?.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  useEffect(() => {
    setMatchIndex(matchingIds.length ? 0 : -1);
  }, [filterText]);
  const handleRunQA = async () => {
    try {
      const data = await aiAPI.runQA(projectId || context?.project_id);
      setDebugEvents((prev) => [
        ...prev,
        { type: 'qa', time: new Date(), payload: data },
      ]);
      const summary = `QA summary: ${data.tables_with_issues} tables with issues, ${data.total_missing_rows} rows missing required fields.`;
      const details = (data.tables || []).slice(0, 3).map((t) =>
        `• ${t.module_name} / ${t.table_title}: ${t.missing_required_rows} rows missing`);
      const content = [summary, ...details].join('\n');

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content,
          timestamp: new Date(),
          metadata: { qa: true },
        }
      ]);
    } catch (error) {
      console.error('Failed to run QA:', error);
    }
  };

  const handleOpenDataGaps = async () => {
    try {
      const data = await aiAPI.runQA(projectId || context?.project_id);
      setDebugEvents((prev) => [
        ...prev,
        { type: 'qa', time: new Date(), payload: data },
      ]);
      const first = (data.tables || []).find((t) => t.missing_required_rows > 0);
      if (first?.action_url) {
        navigate(first.action_url);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: 'assistant',
            content: 'No missing required data detected. Your dataset looks complete ✅',
            timestamp: new Date(),
            metadata: { qa: true },
          }
        ]);
      }
    } catch (error) {
      console.error('Failed to open data gaps:', error);
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
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        overscrollBehavior: 'contain',
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, bgcolor: 'primary.main', color: 'white' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SmartToy />
          <Typography variant="h6" sx={{ flex: 1 }}>Carbon AI Copilot</Typography>
          <Tooltip title="Debug panel">
            <IconButton
              size="small"
              onClick={() => setDebugOpen((v) => !v)}
              sx={{ color: 'white' }}
            >
              <BugReport fontSize="small" />
            </IconButton>
          </Tooltip>
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
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {/* Chat Tab */}
        {activeTab === 0 && (
          <>
            {/* Messages Area */}
            <Box
              sx={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                p: 2,
                bgcolor: 'grey.50',
                overscrollBehavior: 'contain',
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
                  <ChatMessage
                    key={message.id}
                    message={message}
                    onCopy={handleCopyMessage}
                    onReact={handleReact}
                    onTogglePin={handleTogglePin}
                    onToggleSources={handleToggleSources}
                    containerRef={(el) => {
                      if (el) messageRefs.current[message.id] = el;
                    }}
                    isMatch={matchingIds.includes(message.id)}
                  />
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

            {/* Compact Action Bar */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 2,
              py: 0.5,
              bgcolor: 'grey.50',
              borderTop: '1px solid',
              borderColor: 'divider',
              flexShrink: 0,
            }}>
              <Tooltip title="Retry last message">
                <span>
                  <IconButton size="small" onClick={handleRetryLast} disabled={!lastUserMessage || loading}>
                    <Replay fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Stop streaming">
                <span>
                  <IconButton size="small" onClick={handleStop} disabled={!streaming}>
                    <StopCircle fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Restore last cleared (local)">
                <span>
                  <IconButton size="small" onClick={handleRestoreHistory} disabled={!clearedMessages.length}>
                    <Restore fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Clear history">
                <span>
                  <IconButton size="small" onClick={handleClearHistory} disabled={!messages.length}>
                    <Delete fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Reload history">
                <IconButton size="small" onClick={loadChatHistory}>
                  <History fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Export history (JSON + CSV)">
                <span>
                  <IconButton size="small" onClick={handleExportHistory} disabled={!messages.length}>
                    <Download fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Open data gaps">
                <IconButton size="small" onClick={handleOpenDataGaps}>
                  <WarningAmber fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Run QA checks">
                <IconButton size="small" onClick={handleRunQA}>
                  <FactCheck fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Debug panel">
                <IconButton size="small" onClick={() => setDebugOpen((v) => !v)}>
                  <BugReport fontSize="small" />
                </IconButton>
              </Tooltip>
              <Box sx={{ flex: 1 }} />
              <TextField
                size="small"
                placeholder="Filter"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                sx={{ maxWidth: 180 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <Tooltip title="Previous match">
                <span>
                  <IconButton size="small" onClick={() => jumpToMatch(matchIndex - 1)} disabled={!matchingIds.length}>
                    <KeyboardArrowUp fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Next match">
                <span>
                  <IconButton size="small" onClick={() => jumpToMatch(matchIndex + 1)} disabled={!matchingIds.length}>
                    <KeyboardArrowDown fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Paste from clipboard">
                <IconButton size="small" onClick={handlePasteToInput}>
                  <ContentPaste fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>

            {/* Input Area */}
            <Box sx={{ p: 2, bgcolor: 'background.paper', flexShrink: 0 }}>
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
            {debugOpen && (
              <Box sx={{
                borderTop: '1px solid',
                borderColor: 'divider',
                bgcolor: 'grey.100',
                p: 1,
                maxHeight: 180,
                overflowY: 'auto',
              }}>
                <Typography variant="caption" color="text.secondary">
                  Debug feed (AI + QA)
                </Typography>
                {debugEvents.length === 0 ? (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    No debug events yet.
                  </Typography>
                ) : (
                  debugEvents.slice(-8).map((evt, i) => (
                    <Box key={`${evt.type}-${i}`} sx={{ mt: 0.5 }}>
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {evt.type.toUpperCase()} • {evt.time.toLocaleTimeString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(evt.payload)}
                      </Typography>
                    </Box>
                  ))
                )}
              </Box>
            )}
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
