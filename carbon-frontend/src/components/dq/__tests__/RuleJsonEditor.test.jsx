import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import RuleJsonEditor from '../RuleJsonEditor';
import dqRuleSchema from '../dqRuleSchema.json';

const monacoState = vi.hoisted(() => ({
  editorProps: null,
  setDiagnosticsOptions: vi.fn(),
}));

vi.mock('@monaco-editor/react', () => ({
  default: (props) => {
    monacoState.editorProps = props;
    props.beforeMount?.({
      languages: {
        json: {
          jsonDefaults: {
            setDiagnosticsOptions: monacoState.setDiagnosticsOptions,
          },
        },
      },
    });
    return null;
  },
}));

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../../../theme/useThemeMode', () => ({
  useThemeMode: () => ({ mode: 'light' }),
}));

vi.mock('../../NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn() }),
}));

vi.mock('../../../api/dq', () => ({
  createDQJob: vi.fn(),
  getDQJob: vi.fn(),
  listDQSuggestions: vi.fn(),
}));

describe('RuleJsonEditor Monaco wiring', () => {
  beforeEach(() => {
    monacoState.editorProps = null;
    monacoState.setDiagnosticsOptions.mockClear();
  });

  it('renders and wires Monaco value/schema diagnostics', () => {
    const onChange = vi.fn();
    const value = '{\n  "name": "rule"\n}';

    render(
      <RuleJsonEditor
        value={value}
        onChange={onChange}
        tables={[]}
      />
    );

    expect(monacoState.editorProps).toBeTruthy();
    expect(monacoState.editorProps.value).toBe(value);
    expect(typeof monacoState.editorProps.beforeMount).toBe('function');

    expect(monacoState.setDiagnosticsOptions).toHaveBeenCalledTimes(1);
    expect(monacoState.setDiagnosticsOptions).toHaveBeenCalledWith({
      validate: true,
      allowComments: false,
      schemas: [
        {
          uri: dqRuleSchema.$id,
          fileMatch: ['*'],
          schema: dqRuleSchema,
        },
      ],
    });
  });
});
