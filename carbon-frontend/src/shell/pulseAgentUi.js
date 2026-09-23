// Pulse Agent workspace UI (mode toggle + AITaskPanel / DiscoveryComposer).
// Default OFF — Chat + host My/Team/People are the product surfaces.
// Debug re-enable: localStorage carbon-ai-agent-ui=on
// Or build-time: VITE_PULSE_AGENT_UI=true

const STORAGE_KEY = 'carbon-ai-agent-ui';

function envEnabled() {
  try {
    return String(import.meta.env.VITE_PULSE_AGENT_UI || '')
      .toLowerCase() === 'true';
  } catch {
    return false;
  }
}

/**
 * Whether the Pulse Agent mode surface is available in the workspace.
 * @returns {boolean}
 */
export function isPulseAgentUiEnabled() {
  if (envEnabled()) return true;
  try {
    return localStorage.getItem(STORAGE_KEY) === 'on';
  } catch {
    return false;
  }
}

export const PULSE_AGENT_UI_STORAGE_KEY = STORAGE_KEY;
