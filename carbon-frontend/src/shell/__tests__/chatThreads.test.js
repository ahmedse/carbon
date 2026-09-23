import { describe, expect, it } from 'vitest';
import {
  MAIN_THREAD_ID,
  addThread,
  assignToThread,
  claimUnassigned,
  messagesForThread,
  setActiveThread,
  titleFromContent,
} from '../chatThreads';

function baseState() {
  return {
    activeId: MAIN_THREAD_ID,
    threads: [{ id: MAIN_THREAD_ID, titleKey: 'mainThread', title: null, fromMessageId: null }],
    membership: {},
  };
}

describe('chatThreads', () => {
  it('titleFromContent truncates with ellipsis', () => {
    expect(titleFromContent('short')).toBe('short');
    expect(titleFromContent('x'.repeat(50)).endsWith('…')).toBe(true);
  });

  it('addThread switches active and uses newThread key when untitled', () => {
    const next = addThread(baseState(), {});
    expect(next.activeId).not.toBe(MAIN_THREAD_ID);
    expect(next.threads).toHaveLength(2);
    expect(next.threads[1].titleKey).toBe('newThread');
  });

  it('assign + messagesForThread isolates topics', () => {
    let state = addThread(baseState(), { title: 'Leave balance' });
    const topicId = state.activeId;
    state = assignToThread(state, ['m1', 'm2'], topicId);
    state = assignToThread(state, ['m0'], MAIN_THREAD_ID);
    state = setActiveThread(state, MAIN_THREAD_ID);
    const msgs = [
      { id: 'm0', content: 'main' },
      { id: 'm1', content: 'leave' },
      { id: 'm2', content: 'follow' },
    ];
    expect(messagesForThread(msgs, state).map((m) => m.id)).toEqual(['m0']);
    state = setActiveThread(state, topicId);
    expect(messagesForThread(msgs, state).map((m) => m.id)).toEqual(['m1', 'm2']);
  });

  it('claimUnassigned puts orphan messages on active thread', () => {
    const claimed = claimUnassigned(baseState(), [{ id: 'a' }, { id: 'b' }], MAIN_THREAD_ID);
    expect(claimed.membership.a).toBe(MAIN_THREAD_ID);
    expect(claimed.membership.b).toBe(MAIN_THREAD_ID);
  });
});
