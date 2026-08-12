import { useContext } from 'react';
import { AITaskTransferContext } from './aiTaskTransferContext';

export function useAITaskTransfer() {
  const ctx = useContext(AITaskTransferContext);
  if (!ctx) {
    return { transferTask: () => {}, pendingTransferId: null, clearPendingTransfer: () => {} };
  }
  return ctx;
}