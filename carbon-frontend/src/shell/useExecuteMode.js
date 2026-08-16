import { useContext } from 'react';
import { ExecuteModeContext } from './executeModeContext';

/**
 * Access the shared Execute Mode toggle. Falls back to a safe no-op
 * (mode OFF, no mutation) when rendered outside an ExecuteModeProvider,
 * so presentational components stay testable in isolation.
 */
export function useExecuteMode() {
  const ctx = useContext(ExecuteModeContext);
  if (!ctx) {
    return { executeMode: false, setExecuteMode: () => {} };
  }
  return ctx;
}
