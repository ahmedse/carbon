// src/shell/AIAgentPanel.jsx
// Sprint W2-A — Agent surface: Agents / MCP / Tools / Logs internal tabs
// (RULE_17 — MUI Tabs + localStorage key carbon-ai-agent-tab). Agents and
// Tools launch clustered runs via AIActionRunner; MCP is read-only; Logs
// renders durable ToolExecution + LLMCallLog rows from the Pulse read API.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js and
// src/api/aiWorkspace.js); RULE_21: staged mutations confirm in the runner.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { createConversation } from '../api/aiWorkspace';
import { getPulseData, getSettings } from '../api/aiPulse';
import AIActionRunner from './AIActionRunner';

dayjs.extend(utc);
dayjs.extend(timezone);

const AGENT_TAB_KEY = 'carbon-ai-agent-tab';
const PROJECT_TIMEZONE = 'Africa/Cairo';

const formatWhen = (value) => {
  if (!value) return '';
  const parsed = dayjs(value);
  if (!parsed.isValid()) return '';
  return parsed.tz(PROJECT_TIMEZONE).format('MMM D, YYYY · HH:mm');
};

// ── Args form rendered from the tool's JSON parameters schema ─────────────
function ArgsForm({ parameters, value, onChange }) {
  const properties = parameters?.properties || {};
  const keys = Object.keys(properties);
  if (keys.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
        This tool takes no arguments.
      </Typography>
    );
  }
  return (
    <Stack spacing={1}>
      {keys.map((key) => {
        const spec = properties[key] || {};
        const type = spec.type || 'string';
        const current = value[key];
        if (type === 'boolean') {
          return (
            <Stack key={key} direction="row" alignItems="center" spacing={1}>
              <Switch
                size="small"
                checked={Boolean(current)}
                onChange={(e) => onChange({ ...value, [key]: e.target.checked })}
                inputProps={{ 'aria-label': key }}
              />
              <Typography variant="caption" sx={{ fontSize: '0.6875rem' }}>
                {key}
                {spec.description ? ` — ${spec.description}` : ''}
              </Typography>
            </Stack>
          );
        }
        const isJson = type === 'object' || type === 'array';
        return (
          <TextField
            key={key}
            size="small"
            label={key}
            placeholder={spec.description || ''}
            type={type === 'number' || type === 'integer' ? 'number' : 'text'}
            multiline={isJson}
            minRows={isJson ? 2 : 1}
            value={current ?? ''}
            onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            sx={{
              '& .MuiInputBase-root': { fontSize: '0.75rem' },
              '& .MuiInputLabel-root': { fontSize: '0.75rem' },
            }}
          />
        );
      })}
    </Stack>
  );
}

ArgsForm.propTypes = {
  parameters: PropTypes.object,
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
};

// ── Expandable durable-log row (JSON bodies scroll, never widen) ──────────
function LogRow({ row }) {
  const [open, setOpen] = useState(false);
  const timestamp =
    formatWhen(row.executed_at) ||
    formatWhen(row.occurred_at) ||
    formatWhen(row.created_at) ||
    formatWhen(row.updated_at);
  const title = row.name || row.tool || row.id || row.message_id || row.type || 'Record';
  const status = row.status;

  return (
    <Paper variant="outlined" sx={{ borderRadius: 1 }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.75}
        sx={{ px: 0.875, py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
        onClick={() => setOpen((v) => !v)}
      >
        <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={`Toggle ${title} details`}>
          {open ? <ExpandMoreIcon sx={{ fontSize: 15 }} /> : <ChevronRightIcon sx={{ fontSize: 15 }} />}
        </IconButton>
        <Chip size="small" variant="outlined" label={row._type || 'record'} sx={{ height: 18, fontSize: '0.625rem' }} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 500, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title}
        </Typography>
        {status && <Chip size="small" variant="outlined" label={status} sx={{ height: 18, fontSize: '0.625rem' }} />}
        {timestamp && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', flexShrink: 0 }}>
            {timestamp}
          </Typography>
        )}
      </Stack>
      {open && (
        <Box sx={{ px: 1, pb: 0.875 }}>
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 1,
              borderRadius: 1,
              bgcolor: 'action.hover',
              fontSize: '0.6875rem',
              lineHeight: 1.45,
              maxHeight: 240,
              overflow: 'auto',
              whiteSpace: 'pre',
            }}
          >
            {JSON.stringify(row, null, 2)}
          </Box>
        </Box>
      )}
    </Paper>
  );
}

LogRow.propTypes = { row: PropTypes.object.isRequired };

function SectionTitle({ children }) {
  return (
    <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
      {children}
    </Typography>
  );
}

SectionTitle.propTypes = { children: PropTypes.node };

/**
 * Agent surface panel — one activity-bar icon, four internal views.
 * @param {object} props
 * @param {string|null} props.conversationId - anchor conversation (lazily created if none)
 */
function AIAgentPanel({ conversationId: initialConversationId }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  // Notification callbacks may be re-created by context providers — read via a
  // ref so the load/run callbacks depend only on stable inputs (token) and a
  // provider identity change can never re-fire a mount effect (no setState loop).
  const notifyFromErrorRef = useRef(notifyFromError);
  notifyFromErrorRef.current = notifyFromError;

  const [tab, setTab] = useState(() => {
    try {
      return localStorage.getItem(AGENT_TAB_KEY) || 'agents';
    } catch {
      return 'agents';
    }
  });
  const [settings, setSettings] = useState({ agents: [], mcp_servers: [], tools_catalog: [] });
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState(null);

  const [logs, setLogs] = useState({ tools: [], calls: [] });
  const [logsLoading, setLogsLoading] = useState(false);

  const [conversationId, setConversationId] = useState(initialConversationId || null);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [run, setRun] = useState(null);
  const [running, setRunning] = useState(false);
  const [verbosity, setVerbosity] = useState('concise');

  const [selectedTool, setSelectedTool] = useState(null);
  const [toolArgs, setToolArgs] = useState({});

  const handleTabChange = useCallback((e, value) => {
    setTab(value);
    try {
      localStorage.setItem(AGENT_TAB_KEY, value);
    } catch {
      // storage may be unavailable — tab still switches in-memory
    }
  }, []);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const data = await getSettings(token);
      setSettings({
        agents: Array.isArray(data?.agents) ? data.agents : [],
        mcp_servers: Array.isArray(data?.mcp_servers) ? data.mcp_servers : [],
        tools_catalog: Array.isArray(data?.tools_catalog) ? data.tools_catalog : [],
      });
    } catch (err) {
      setSettingsError(err.message || 'Could not load the agent catalog');
      notifyFromErrorRef.current(err, 'Could not load the agent catalog');
    } finally {
      setSettingsLoading(false);
    }
  }, [token]);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const [toolData, logData] = await Promise.all([
        getPulseData(token, 'tools'),
        getPulseData(token, 'logs'),
      ]);
      setLogs({
        tools: Array.isArray(toolData?.results) ? toolData.results : [],
        calls: Array.isArray(logData?.results)
          ? logData.results.filter((row) => row?._type === 'LLMCallLog')
          : [],
      });
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not load logs');
    } finally {
      setLogsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (tab === 'logs' && logs.tools.length === 0 && logs.calls.length === 0) {
      loadLogs();
    }
  }, [tab, loadLogs, logs]);

  // ── Run launcher — lazily creates an anchor conversation if needed ──────
  const startRun = useCallback(
    async (spec) => {
      let convId = conversationId;
      if (!convId) {
        setCreatingConversation(true);
        try {
          const conv = await createConversation(token, {
            conversation_type: 'chat',
            title: 'Agent run',
          });
          convId = conv.id;
          setConversationId(conv.id);
        } catch (err) {
          notifyFromErrorRef.current(err, 'Could not start the run');
          return;
        } finally {
          setCreatingConversation(false);
        }
      }
      setRun({ runId: Date.now(), ...spec, verbosity });
    },
    [conversationId, token, verbosity],
  );

  const mcpTools = useMemo(
    () => settings.tools_catalog.filter((t) => t.kind === 'mcp'),
    [settings.tools_catalog],
  );

  const selectTool = useCallback(
    (tool) => {
      setSelectedTool(tool);
      const defaults = {};
      const properties = tool?.parameters?.properties || {};
      Object.entries(properties).forEach(([key, spec]) => {
        if (spec?.type === 'boolean') defaults[key] = Boolean(spec.default);
        else if (spec?.default !== undefined) defaults[key] = spec.default;
        else if (spec?.type === 'number' || spec?.type === 'integer') defaults[key] = 0;
        else defaults[key] = '';
      });
      setToolArgs(defaults);
    },
    [],
  );

  const runBusy = running || creatingConversation;

  const renderAgents = () => {
    if (settingsLoading) {
      return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={22} /></Box>;
    }
    if (settingsError) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 3, px: 1 }}>
          <CloudOffIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
            Agent catalog unavailable — {settingsError}
          </Typography>
        </Box>
      );
    }
    if (settings.agents.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, px: 1, fontSize: '0.75rem' }}>
          No agents registered yet.
        </Typography>
      );
    }
    return (
      <Stack spacing={1}>
        {settings.agents.map((agent) => (
          <Paper key={agent.id} variant="outlined" sx={{ p: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                  {agent.name}
                </Typography>
                {agent.role && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
                    {agent.role}
                  </Typography>
                )}
                {Array.isArray(agent.tool_set) && agent.tool_set.length > 0 && (
                  <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                    {agent.tool_set.map((toolName) => (
                      <Chip key={toolName} size="small" variant="outlined" label={toolName} sx={{ height: 18, fontSize: '0.625rem' }} />
                    ))}
                  </Stack>
                )}
              </Box>
              <Button
                size="small"
                variant="contained"
                disabled={runBusy}
                onClick={() => startRun({ action_type: 'agent', agent: agent.name, args: {} })}
                sx={{ fontSize: '0.6875rem', textTransform: 'none', flexShrink: 0 }}
              >
                Run
              </Button>
            </Stack>
          </Paper>
        ))}
      </Stack>
    );
  };

  const renderMcp = () => {
    if (settingsLoading) {
      return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={22} /></Box>;
    }
    if (settings.mcp_servers.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, px: 1, fontSize: '0.75rem' }}>
          No MCP servers configured.
        </Typography>
      );
    }
    return (
      <Stack spacing={1}>
        <SectionTitle>MCP servers</SectionTitle>
        {settings.mcp_servers.map((server) => (
          <Paper key={server.name} variant="outlined" sx={{ p: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
              {server.name}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
              {server.command} {Array.isArray(server.args) ? server.args.join(' ') : ''}
            </Typography>
          </Paper>
        ))}
        {mcpTools.length > 0 && (
          <>
            <SectionTitle>MCP tools ({mcpTools.length})</SectionTitle>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              {mcpTools.map((t) => t.name).join(', ')} — run them from the Tools tab.
            </Typography>
          </>
        )}
      </Stack>
    );
  };

  const renderTools = () => {
    if (settingsLoading) {
      return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={22} /></Box>;
    }
    if (settings.tools_catalog.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, px: 1, fontSize: '0.75rem' }}>
          No tools registered yet.
        </Typography>
      );
    }
    return (
      <Stack spacing={1}>
        <FormControl size="small" fullWidth>
          <InputLabel id="agent-tool-select-label" sx={{ fontSize: '0.75rem' }}>Tool</InputLabel>
          <Select
            labelId="agent-tool-select-label"
            label="Tool"
            value={selectedTool?.name ?? ''}
            onChange={(e) => selectTool(settings.tools_catalog.find((t) => t.name === e.target.value) || null)}
            sx={{ '& .MuiSelect-select': { fontSize: '0.75rem', py: 0.875 } }}
          >
            {settings.tools_catalog.map((tool) => (
              <MenuItem key={tool.name} value={tool.name} sx={{ fontSize: '0.75rem' }}>
                {tool.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {settings.tools_catalog.map((tool) => (
          <Paper
            key={tool.name}
            variant="outlined"
            sx={{ p: 1, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
            onClick={() => selectTool(tool)}
          >
            <Stack direction="row" alignItems="center" spacing={0.75}>
              <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {tool.name}
              </Typography>
              <Chip size="small" variant="outlined" label={tool.kind || 'tool'} sx={{ height: 18, fontSize: '0.625rem' }} />
              {tool.requires_confirmation && (
                <Chip size="small" color="warning" variant="outlined" label="approval" sx={{ height: 18, fontSize: '0.625rem' }} />
              )}
            </Stack>
            {tool.description && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25, fontSize: '0.6875rem' }}>
                {tool.description}
              </Typography>
            )}
          </Paper>
        ))}

        {selectedTool && (
          <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', mb: 1 }}>
              Run {selectedTool.name}
            </Typography>
            <ArgsForm parameters={selectedTool.parameters} value={toolArgs} onChange={setToolArgs} />
            <Button
              size="small"
              variant="contained"
              disabled={runBusy}
              onClick={() => startRun({ action_type: 'tool', tool: selectedTool.name, args: toolArgs })}
              sx={{ mt: 1, fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Run tool
            </Button>
          </Paper>
        )}
      </Stack>
    );
  };

  const renderLogs = () => (
    <Stack spacing={1.25}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <SectionTitle>Tool executions</SectionTitle>
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Refresh logs">
          <IconButton size="small" onClick={loadLogs} aria-label="Refresh logs">
            <RefreshIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Tooltip>
      </Stack>
      {logsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
      ) : logs.tools.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          No tool executions recorded yet.
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {logs.tools.map((row) => (
            <LogRow key={`${row._type}-${row.id}`} row={row} />
          ))}
        </Stack>
      )}

      <Divider sx={{ my: 0.5 }} />
      <SectionTitle>AI call logs</SectionTitle>
      {logsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
      ) : logs.calls.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          No LLM calls recorded yet.
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {logs.calls.map((row) => (
            <LogRow key={`${row._type}-${row.id}`} row={row} />
          ))}
        </Stack>
      )}
    </Stack>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, bgcolor: 'background.default' }}>
      {/* Internal views — one Agent icon, four tabs (RULE_17) */}
      <Box sx={{ px: 1, pt: 0.5, borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          variant="fullWidth"
          aria-label="Agent views"
          sx={{
            minHeight: 34,
            '& .MuiTab-root': { minHeight: 34, fontSize: '0.6875rem', py: 0.5 },
          }}
        >
          <Tab value="agents" label="Agents" />
          <Tab value="mcp" label="MCP" />
          <Tab value="tools" label="Tools" />
          <Tab value="logs" label="Logs" />
        </Tabs>
      </Box>

      {/* Tab content */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
        {tab === 'agents' ? renderAgents()
          : tab === 'mcp' ? renderMcp()
            : tab === 'tools' ? renderTools()
              : renderLogs()}
      </Box>

      {/* Run dock — clustered timeline + verbosity for the next run */}
      <Box
        sx={{
          borderTop: 1,
          borderColor: 'divider',
          px: 1,
          py: 0.75,
          maxHeight: '45%',
          minHeight: 64,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
          bgcolor: 'background.paper',
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
            Run
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            Detail
          </Typography>
          <Select
            size="small"
            value={verbosity}
            onChange={(e) => setVerbosity(e.target.value)}
            aria-label="Run detail"
            sx={{ '& .MuiSelect-select': { fontSize: '0.6875rem', py: 0.5 } }}
          >
            <MenuItem value="concise" sx={{ fontSize: '0.75rem' }}>Concise</MenuItem>
            <MenuItem value="full" sx={{ fontSize: '0.75rem' }}>Full</MenuItem>
          </Select>
        </Stack>
        <AIActionRunner
          token={token}
          conversationId={conversationId}
          run={run}
          onPhaseChange={(phase) => setRunning(phase === 'working')}
        />
      </Box>
    </Box>
  );
}

AIAgentPanel.propTypes = {
  conversationId: PropTypes.string,
};

export default AIAgentPanel;
