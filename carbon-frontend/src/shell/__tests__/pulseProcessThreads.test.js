import { beforeEach, describe, expect, it } from 'vitest';
import {
  PROCESS_BY_CONV_KEY,
  PROCESS_LAST_KEY,
  findConversationForProcess,
  lastConversationForProcess,
  normalizePulseProcess,
  processCreatePayload,
  processForConversation,
  rememberConversationProcess,
} from '../pulseProcessThreads';

describe('pulseProcessThreads', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults unknown process to ask', () => {
    expect(normalizePulseProcess('plan')).toBe('plan');
    expect(normalizePulseProcess('ask')).toBe('ask');
    expect(normalizePulseProcess('other')).toBe('ask');
  });

  it('reads process from task_payload and remembers last per dial', () => {
    const plan = { id: 'p1', task_payload_json: { pulse_mode: 'plan' } };
    const ask = { id: 'a1', task_payload: { pulse_process: 'ask' } };
    expect(processForConversation(plan)).toBe('plan');
    expect(processForConversation(ask)).toBe('ask');

    rememberConversationProcess('p1', 'plan');
    rememberConversationProcess('a1', 'ask');
    expect(JSON.parse(localStorage.getItem(PROCESS_BY_CONV_KEY))).toEqual({
      p1: 'plan',
      a1: 'ask',
    });
    expect(lastConversationForProcess('plan', ['p1', 'a1'])).toBe('p1');
    expect(lastConversationForProcess('ask', ['p1', 'a1'])).toBe('a1');
    expect(lastConversationForProcess('plan', ['a1'])).toBeNull();
  });

  it('findConversationForProcess prefers a tagged open thread', () => {
    rememberConversationProcess('stale-plan', 'plan');
    const list = [
      { id: 'ask-open', task_payload_json: { pulse_mode: 'ask' } },
      { id: 'plan-open', task_payload_json: { pulse_mode: 'plan' } },
    ];
    expect(findConversationForProcess('plan', list)).toBe('plan-open');
    expect(findConversationForProcess('ask', list)).toBe('ask-open');
  });

  it('processCreatePayload tags the dial', () => {
    expect(processCreatePayload('plan', 'Plan')).toEqual({
      conversation_type: 'chat',
      title: 'Plan',
      task_payload: { pulse_process: 'plan' },
    });
    expect(JSON.parse(localStorage.getItem(PROCESS_LAST_KEY) || '{}')).toEqual({});
  });
});
