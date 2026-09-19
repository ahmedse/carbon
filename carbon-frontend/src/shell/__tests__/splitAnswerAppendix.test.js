import { describe, expect, it } from 'vitest';
import { splitAnswerAppendix } from '../splitAnswerAppendix';

describe('splitAnswerAppendix', () => {
  it('keeps prose and peels toolish json/python fences', () => {
    const md = [
      'The population is predominantly full-time (533, 99.3%).',
      '',
      '```json',
      '{"api_name": "analyze_employees", "params": {"dimension": "employment_status"}}',
      '```',
      '',
      '```python',
      "result = data.sort_values(by='count', ascending=False)",
      '```',
    ].join('\n');

    const { prose, appendix, hasAppendix } = splitAnswerAppendix(md);
    expect(prose).toBe('The population is predominantly full-time (533, 99.3%).');
    expect(hasAppendix).toBe(true);
    expect(appendix).toMatch(/analyze_employees/);
    expect(appendix).toMatch(/sort_values/);
  });

  it('leaves non-tool fences in prose', () => {
    const md = 'See example:\n\n```markdown\n# Title\n```\n';
    const { prose, hasAppendix } = splitAnswerAppendix(md);
    expect(prose).toMatch(/```markdown/);
    expect(hasAppendix).toBe(false);
  });

  it('falls back to full markdown when only fences remain', () => {
    const md = '```json\n{"a":1}\n```';
    const { prose, hasAppendix } = splitAnswerAppendix(md);
    expect(hasAppendix).toBe(false);
    expect(prose).toMatch(/\{"a":1\}/);
  });
});
