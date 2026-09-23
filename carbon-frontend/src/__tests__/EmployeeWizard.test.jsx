// NSR-4B — EmployeeWizard: manager/join_date validation + opening_basic payload.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: () => ({ options: [], loading: false, error: null }),
}));

vi.mock('../components/MicroHelp', () => ({
  default: () => null,
}));

vi.mock('../api/people', () => ({
  fetchEmployees: vi.fn(async () => ({
    count: 1,
    results: [{ id: 5, employee_no: '1001', full_name: 'Sara Manager' }],
  })),
}));

import EmployeeWizard from '../apps/people/EmployeeWizard';
import { buildEmployeeWizardPayload } from '../apps/people/employeeWizardPayload';

const ORG_UNITS = [{ id: 1, name: 'Ops', code: 'OPS' }];
const POSITIONS = [{ id: 10, title: 'Engineer', code: 'ENG' }];
const EMPLOYEES = [
  { id: 5, employee_no: '1001', full_name: 'Sara Manager' },
];

function baseForm(overrides = {}) {
  return {
    org_unit: '1',
    employee_no: '2048',
    full_name: 'New Hire',
    name_en_given: '',
    name_en_family: '',
    name_ar_given: '',
    name_ar_family: '',
    nationality: '',
    gender: '',
    civil_id: '',
    date_of_birth: '',
    employment_type: '',
    contract_type: '',
    kuwaitization: false,
    basic_salary: '',
    opening_basic: '',
    join_date: '2026-09-01',
    rotation: '',
    position: '',
    manager: '5',
    is_active: true,
    ...overrides,
  };
}

describe('buildEmployeeWizardPayload (NSR-4B / NSR-7C)', () => {
  it('includes opening_basic when set and never sends basic_salary', () => {
    const payload = buildEmployeeWizardPayload(
      baseForm({ opening_basic: '850.500', basic_salary: '999' }),
    );
    expect(payload.opening_basic).toBe('850.500');
    expect(payload).not.toHaveProperty('basic_salary');
    expect(payload.manager).toBe(5);
    expect(payload.join_date).toBe('2026-09-01');
  });

  it('omits opening_basic when empty or whitespace', () => {
    expect(buildEmployeeWizardPayload(baseForm({ opening_basic: '' })))
      .not.toHaveProperty('opening_basic');
    expect(buildEmployeeWizardPayload(baseForm({ opening_basic: '   ' })))
      .not.toHaveProperty('opening_basic');
  });

  it('omits opening_basic when includeOpeningBasic is false (edit)', () => {
    const payload = buildEmployeeWizardPayload(
      baseForm({ opening_basic: '100' }),
      { includeOpeningBasic: false },
    );
    expect(payload).not.toHaveProperty('opening_basic');
  });

  it('emits governed FK field names as codes, never *_code keys', () => {
    const payload = buildEmployeeWizardPayload(baseForm({
      nationality: 'EGY',
      gender: 'male',
      employment_type: 'permanent',
      contract_type: 'fixed-term',
      rotation: 'office',
    }));
    expect(payload.nationality).toBe('EGY');
    expect(payload.gender).toBe('male');
    expect(payload.employment_type).toBe('permanent');
    expect(payload.contract_type).toBe('fixed-term');
    expect(payload.rotation).toBe('office');
    expect(payload).not.toHaveProperty('nationality_code');
    expect(payload).not.toHaveProperty('employment_type_code');
    expect(payload).not.toHaveProperty('contract_type_code');
  });
});

describe('EmployeeWizard validation (NSR-4B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('blocks employment Next without manager; requires join_date', async () => {
    const onSave = vi.fn();
    render(
      <EmployeeWizard
        orgUnits={ORG_UNITS}
        positions={POSITIONS}
        token="tok"
        employees={EMPLOYEES}
        canViewCompensation
        saving={false}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'New Hire' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByLabelText(/Employee No/i), {
      target: { value: '2048' },
    });
    // Org unit autocomplete
    const orgInput = screen.getByLabelText(/Organisation Unit|Org Unit|Organisation/i);
    fireEvent.mouseDown(orgInput);
    fireEvent.click(await screen.findByText('Ops'));

    fireEvent.change(screen.getByLabelText(/Join Date/i), {
      target: { value: '2026-09-01' },
    });
    // Manager intentionally left empty
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(await screen.findByText(/Manager is required/i)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('shows opening_basic when compensation-capable create; payload includes it on finish', async () => {
    const onSave = vi.fn();
    render(
      <EmployeeWizard
        orgUnits={ORG_UNITS}
        positions={POSITIONS}
        token="tok"
        employees={EMPLOYEES}
        canViewCompensation
        saving={false}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'New Hire' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByLabelText(/Employee No/i), {
      target: { value: '2048' },
    });
    const orgInput = screen.getByLabelText(/Organisation Unit|Org Unit|Organisation/i);
    fireEvent.mouseDown(orgInput);
    fireEvent.click(await screen.findByText('Ops'));

    const mgrInput = screen.getByLabelText(/^Manager/i);
    fireEvent.mouseDown(mgrInput);
    fireEvent.click(await screen.findByText(/1001 — Sara Manager/i));

    fireEvent.change(screen.getByLabelText(/Join Date/i), {
      target: { value: '2026-09-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    const opening = await screen.findByTestId('wizard-opening-basic');
    fireEvent.change(opening, { target: { value: '975.000' } });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    // Review → Save
    expect(await screen.findByText(/Review the details/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Save/i }));

    expect(onSave).toHaveBeenCalledTimes(1);
    const payload = onSave.mock.calls[0][0];
    expect(payload.opening_basic).toBe('975.000');
    expect(payload).not.toHaveProperty('basic_salary');
    expect(payload.manager).toBe(5);
    expect(payload.join_date).toBe('2026-09-01');
  });

  it('hides opening_basic when canViewCompensation is false', async () => {
    render(
      <EmployeeWizard
        orgUnits={ORG_UNITS}
        positions={POSITIONS}
        token="tok"
        employees={EMPLOYEES}
        canViewCompensation={false}
        saving={false}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'New Hire' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByLabelText(/Employee No/i), {
      target: { value: '2048' },
    });
    const orgInput = screen.getByLabelText(/Organisation Unit|Org Unit|Organisation/i);
    fireEvent.mouseDown(orgInput);
    fireEvent.click(await screen.findByText('Ops'));

    const mgrInput = screen.getByLabelText(/^Manager/i);
    fireEvent.mouseDown(mgrInput);
    fireEvent.click(await screen.findByText(/1001 — Sara Manager/i));

    fireEvent.change(screen.getByLabelText(/Join Date/i), {
      target: { value: '2026-09-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(await screen.findByText(/Opening basic seeds|Optional opening basic/i)).toBeInTheDocument();
    expect(screen.queryByTestId('wizard-opening-basic')).not.toBeInTheDocument();
  });

  it('omits opening_basic from onSave when field left empty', async () => {
    const onSave = vi.fn();
    render(
      <EmployeeWizard
        orgUnits={ORG_UNITS}
        positions={POSITIONS}
        token="tok"
        employees={EMPLOYEES}
        canViewCompensation
        saving={false}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'New Hire' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    fireEvent.change(screen.getByLabelText(/Employee No/i), {
      target: { value: '2048' },
    });
    fireEvent.mouseDown(screen.getByLabelText(/Organisation Unit|Org Unit|Organisation/i));
    fireEvent.click(await screen.findByText('Ops'));
    fireEvent.mouseDown(screen.getByLabelText(/^Manager/i));
    fireEvent.click(await screen.findByText(/1001 — Sara Manager/i));
    fireEvent.change(screen.getByLabelText(/Join Date/i), {
      target: { value: '2026-09-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    expect(await screen.findByTestId('wizard-opening-basic')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    expect(await screen.findByText(/Review the details/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Save/i }));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).not.toHaveProperty('opening_basic');
  });
});
