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
import { createConversation, findOpenConversation, sendMessage } from '../api/aiWorkspace';
import { normalizeAppIdentifier, fetchKnownAppIdentifiers } from './aiTaskTransferUtils';
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

  // Build the entity scope for the resume lookup from the normalized payload.
  // A transfer carries entity identity (table/module); the existing-thread
  // lookup must be scoped to it so a generic 'chat' never resumes a thread
  // that belongs to a DIFFERENT table/module.
  const buildEntityScope = useCallback((normalizedPayload = {}) => {
    const scope = {};
    if (normalizedPayload.table_id != null) scope.table_id = normalizedPayload.table_id;
    if (normalizedPayload.module_id != null) scope.module_id = normalizedPayload.module_id;
    return Object.keys(scope).length > 0 ? scope : null;
  }, []);

  const transferTask = useCallback(
    async (type, payload, metadata = {}) => {
      // Auto-open the copilot pane if hidden
      if (onRequestOpenRef.current) {
        onRequestOpenRef.current();
      }

      // Build conversation title
      const normalizedPayload = enrichPayload(type, payload);
      const appIds = await fetchKnownAppIdentifiers(token);
      const appIdentifier = normalizeAppIdentifier(normalizedPayload, metadata, appIds);
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
        // Phase 16 — resume the most recent open thread of the same kind
        // (one open conversation per type+app) instead of always creating.
        // Scoped to the transferred entity (table/module) so a generic chat
        // never hijacks a thread that belongs to a different entity.
        const entityScope = buildEntityScope(normalizedPayload);
        const existing = await findOpenConversation(token, {
          conversation_type: type,
          app_identifier: appIdentifier || undefined,
          ...(entityScope ? { entityScope } : {}),
        });

        let conv;
        if (existing) {
          conv = existing;
        } else {
          conv = await createConversation(token, {
            conversation_type: type,
            title,
            app_identifier: appIdentifier,
            task_payload: { type, ...normalizedPayload },
            workspace_context: metadata.workspaceContext,
          });
        }
        setPendingTransferId(conv.id);

        // Phase 8-B — one-click trigger: a nl_rule_test transfer with a candidate
        // rule text kicks off the read-only dry-run immediately by sending the NL
        // rule (mirrors the "Test live" button on a DQ suggestion card). The
        // backend accepts the rule as message content or task_payload.nl.
        if (type === 'nl_rule_test' && normalizedPayload.nl) {
          try {
            await sendMessage(token, conv.id, String(normalizedPayload.nl));
          } catch {
            // The conversation still exists; the user can re-trigger from the thread.
          }
        }

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

        // Phase 10-B — one-click trigger: a report_draft transfer with a module
        // or period target kicks off the draft immediately by sending the
        // sentinel message (mirrors the "Draft Report" entry point on the
        // module detail page).
        if (
          type === 'report_draft' &&
          (normalizedPayload.module_id || normalizedPayload.period_id)
        ) {
          try {
            await sendMessage(token, conv.id, 'Draft this report');
          } catch {
            // The conversation still exists; the user can re-trigger from the thread.
          }
        }

        return conv.id;
      } catch (err) {
        notifyFromError(err, 'Could not transfer task to Pulse');
        return null;
      }
    },
    [token, notifyFromError, enrichPayload, buildEntityScope],
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
