// src/shell/AITaskTransferContext.jsx
// React Context enabling any main-workspace page to transfer a task
// to the AI Workspace pane. Transferred tasks become conversations.
//
// Usage:
//   const { transferTask, pendingTransferId } = useAITaskTransfer();
//   transferTask('dq_validate', { rule_id: 42 }, { title: 'DQ Check: emissions_fuel' });

import React, {
  useCallback,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { createConversation, sendMessage } from '../api/aiWorkspace';
import { normalizeAppIdentifier } from './aiTaskTransferUtils';
import { AITaskTransferContext } from './aiTaskTransferContext';

/**
 * Provider that wraps the entire Shell so both the editor (DQ pages)
 * and the AIWorkspace pane can participate in task transfers.
 */
export function AITaskTransferProvider({ children, onRequestOpen }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const onRequestOpenRef = useRef(onRequestOpen);
  onRequestOpenRef.current = onRequestOpen;

  const [pendingTransferId, setPendingTransferId] = useState(null);

  const enrichPayload = useCallback((type, payload = {}) => {
    const base = { ...payload };
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const fields = Array.isArray(payload.fields) ? payload.fields : [];

    if (type === 'nl_query') {
      return {
        ...base,
        table_name: payload.table_name || payload.table || null,
        row_count: payload.row_count ?? null,
        columns,
      };
    }

    if (type === 'dq_suggest') {
      return {
        ...base,
        table_id: payload.table_id ?? null,
        table_name: payload.table_name || payload.table || null,
        row_count: payload.row_count ?? null,
        columns,
        fields,
      };
    }

    if (type === 'anomaly') {
      return {
        ...base,
        table_id: payload.table_id ?? null,
        table_name: payload.table_name || payload.table || null,
        profile_count_hint: payload.profile_count_hint ?? payload.profile_count ?? null,
      };
    }

    if (type === 'dq_validate' || type === 'investigate') {
      return {
        ...base,
        table_id: payload.table_id ?? null,
        table_name: payload.table_name ?? payload.table ?? null,
        row_count: payload.row_count ?? null,
        module_id: payload.module_id ?? null,
        module_name: payload.module_name ?? null,
      };
    }

    if (type === 'report_draft') {
      return {
        ...base,
        module_id: payload.module_id ?? null,
        module_name: payload.module_name ?? null,
        period_id: payload.period_id ?? null,
      };
    }

    if (type === 'chat') {
      return {
        ...base,
        table_id: payload.table_id ?? null,
        table_name: payload.table_name ?? payload.table ?? null,
        module_id: payload.module_id ?? null,
        module_name: payload.module_name ?? null,
      };
    }

    return base;
  }, []);

  const transferTask = useCallback(
    async (type, payload, metadata = {}) => {
      // Auto-open the copilot pane if hidden
      if (onRequestOpenRef.current) {
        onRequestOpenRef.current();
      }

      // Build conversation title
      const normalizedPayload = enrichPayload(type, payload);
      const title =
        metadata.title ||
        (type === 'dq_validate'
          ? `DQ: ${normalizedPayload.rule_name || `Rule #${normalizedPayload.rule_id}` || 'Check'}`
          : type === 'dq_suggest'
            ? `Suggest: ${normalizedPayload.table_name || 'Table'}`
            : type === 'anomaly'
              ? `Anomaly: ${normalizedPayload.table_name || 'Table'}`
              : type === 'nl_query'
                ? `Query: ${normalizedPayload.table_name || 'Data'}`
                : 'Chat');

      try {
        const appIdentifier = normalizeAppIdentifier(normalizedPayload, metadata);
        const conv = await createConversation(token, {
          conversation_type: type,
          title,
          app_identifier: appIdentifier,
          task_payload: { type, ...normalizedPayload },
          workspace_context: metadata.workspaceContext,
        });
        setPendingTransferId(conv.id);

        // Phase 9-B — one-click trigger: an investigate transfer with a target
        // table kicks off the read-only pipeline immediately by sending the
        // sentinel message (mirrors the "Investigate" entry point on the table
        // detail page).
        if (type === 'investigate' && normalizedPayload.table_id) {
          try {
            await sendMessage(token, conv.id, 'Investigate this table');
          } catch {
            // The conversation still exists; the user can re-trigger from the thread.
          }
        }

        return conv.id;
      } catch (err) {
        notifyFromError(err, 'Could not transfer task to AI Workspace');
        return null;
      }
    },
    [token, notifyFromError, enrichPayload],
  );

  const clearPendingTransfer = useCallback(() => {
    setPendingTransferId(null);
  }, []);

  const value = useMemo(
    () => ({ transferTask, pendingTransferId, clearPendingTransfer }),
    [transferTask, pendingTransferId, clearPendingTransfer],
  );

  return (
    <AITaskTransferContext.Provider value={value}>
      {children}
    </AITaskTransferContext.Provider>
  );
}
