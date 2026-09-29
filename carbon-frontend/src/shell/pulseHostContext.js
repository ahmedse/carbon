import { createContext, useContext } from 'react';

/** Set when Moodle (or another host) is showing the real Pulse pane. */
export const PulseHostContext = createContext(null);

export function usePulseHost() {
  return useContext(PulseHostContext);
}
