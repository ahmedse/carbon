import { courseThreadId, moodleActivityId, moodleCourseId, moodleThreadKey } from '../pulseHostContext';

describe('moodle course thread', () => {
  it('reads the course id from the signed page block', () => {
    const block = [
      'Moodle audience: staff.',
      'Open course NMD3101: Principles of Infection (NMD3101) id=25 category=Year 3 format=topics.',
    ].join('\n');
    expect(moodleCourseId(block)).toBe('25');
    expect(moodleThreadKey('25')).toBe('pulse-moodle-thread:25');
  });

  it('does not invent a course when the page has none', () => {
    expect(moodleCourseId('No course is open. Do not invent a course page.')).toBe('');
    expect(moodleThreadKey('')).toBe('');
    expect(moodleActivityId('No course is open. Do not invent a course page.')).toBe('');
  });

  it('keeps the same thread when an activity page names a cmid', () => {
    const home = [
      'Moodle audience: staff.',
      'Open course NMD3101: Principles of Infection (NMD3101) id=25 category=Year 3 format=topics.',
    ].join('\n');
    const activity = [
      home,
      'Open activity L11 handout cmid=418.',
    ].join('\n');
    const store = { 'pulse-moodle-thread:25': 'conv-course' };
    const read = (key) => store[key] || '';
    expect(moodleCourseId(activity)).toBe('25');
    expect(moodleActivityId(home)).toBe('');
    expect(moodleActivityId(activity)).toBe('418');
    expect(courseThreadId(home, ['conv-course'], read)).toBe('conv-course');
    expect(courseThreadId(activity, ['conv-course'], read)).toBe('conv-course');
    expect(courseThreadId(activity, ['other'], read)).toBe('');
  });
});
