// src/__tests__/PeoplePages.test.jsx
// Regression guard for the People & Payroll page set (NIR-4A).

import { describe, it, expect, vi } from 'vitest';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { apiFetch } from '../api/api';
import peopleManifest from '../apps/people/manifest';
import * as peopleApi from '../api/people';
import EmployeesPage from '../apps/people/EmployeesPage';
import LeavePage from '../apps/people/LeavePage';
import PayrollRunsPage from '../apps/people/PayrollRunsPage';
import PayslipPage from '../apps/people/PayslipPage';
import BenefitsPage from '../apps/people/BenefitsPage';
import AttendancePage from '../apps/people/AttendancePage';
import PeopleConfigPage from '../apps/people/PeopleConfigPage';
import PositionsPage from '../apps/people/PositionsPage';
import LoansPage from '../apps/people/LoansPage';
import CertificationsPage from '../apps/people/CertificationsPage';
import RotationSchedulesPage from '../apps/people/RotationSchedulesPage';
import { NAV_LABEL_KEYS } from '../i18n/shellLabels';

const PEOPLE_PATHS = [
  '/people',
  '/people/positions',
  '/people/employees',
  '/people/leave',
  '/people/payroll',
  '/people/payslip',
  '/people/benefits',
  '/people/attendance',
  '/people/config',
  '/people/loans',
  '/people/certifications',
  '/people/rotation',
];

describe('People & Payroll pages (NIR-4A)', () => {
  it('registers all /people/* navigation paths', () => {
    const paths = peopleManifest.navigation.items.map((item) => item.path);
    for (const path of PEOPLE_PATHS) {
      expect(paths).toContain(path);
    }
  });

  it('groups navigation items under Workforce, Payroll & Benefits, and Configuration headers', () => {
    const items = peopleManifest.navigation.items;
    for (const label of ['Organization', 'Workforce', 'Payroll & Benefits', 'Configuration']) {
      expect(items.some((i) => i.type === 'group' && i.label === label)).toBe(true);
    }
  });

  it('each page module default-exports a function', () => {
    const pages = [EmployeesPage, LeavePage, PayrollRunsPage, PayslipPage, BenefitsPage, AttendancePage, PeopleConfigPage, PositionsPage, LoansPage, CertificationsPage, RotationSchedulesPage];
    for (const Page of pages) {
      expect(typeof Page).toBe('function');
    }
  });

  it('registers shell nav label keys for Loans, Certifications, and Rotation', () => {
    expect(NAV_LABEL_KEYS.Loans).toBe('nav.loans');
    expect(NAV_LABEL_KEYS.Certifications).toBe('nav.certifications');
    expect(NAV_LABEL_KEYS.Rotation).toBe('nav.rotation');
  });

  it('places Loans under Payroll & Benefits and Certifications/Rotation under Workforce', () => {
    const items = peopleManifest.navigation.items;
    const groupOf = (label) => {
      let currentGroup = null;
      for (const item of items) {
        if (item.type === 'group') {
          currentGroup = item.label;
        } else if (item.label === label) {
          return currentGroup;
        }
      }
      return null;
    };
    expect(groupOf('Loans')).toBe('Payroll & Benefits');
    expect(groupOf('Certifications')).toBe('Workforce');
    expect(groupOf('Rotation')).toBe('Workforce');
  });

  it('exports all People API helper functions', () => {
    const helpers = [
      'fetchEmployees',
      'fetchPayrollRuns',
      'fetchPayrollRun',
      'createPayrollRun',
      'updatePayrollRun',
      'deletePayrollRun',
      'exportWpsPayrollRun',
      'computePayrollRun',
      'validatePayrollRun',
      'commitPayrollRun',
      'fetchPayrollRunValidations',
      'fetchPayslipLines',
      'fetchLeaveEntitlements',
      'fetchLeaveRecords',
      'createLeaveRecord',
      'updateLeaveRecord',
      'deleteLeaveRecord',
      'createLeaveEntitlement',
      'updateLeaveEntitlement',
      'deleteLeaveEntitlement',
      'fetchBenefitTypes',
      'fetchEmployeeBenefits',
      'createBenefitType',
      'updateBenefitType',
      'deleteBenefitType',
      'createEmployeeBenefit',
      'updateEmployeeBenefit',
      'deleteEmployeeBenefit',
      'fetchAttendanceRecords',
      'fetchAttendancePermissions',
      'createAttendanceRecord',
      'updateAttendanceRecord',
      'deleteAttendanceRecord',
      'createAttendancePermission',
      'updateAttendancePermission',
      'deleteAttendancePermission',
      'fetchComplianceRules',
      'fetchPositions',
      'createEmployee',
      'updateEmployee',
      'deleteEmployee',
      'createPosition',
      'updatePosition',
      'deletePosition',
      'fetchLoans',
      'createLoan',
      'updateLoan',
      'deleteLoan',
      'fetchLoanInstallments',
      'fetchCertifications',
      'createCertification',
      'updateCertification',
      'deleteCertification',
      'fetchRotationSchedules',
      'createRotationSchedule',
      'updateRotationSchedule',
      'deleteRotationSchedule',
    ];
    for (const name of helpers) {
      expect(typeof peopleApi[name]).toBe('function');
    }
  });

  it('builds the payroll_run query for payslip lines', () => {
    peopleApi.fetchPayslipLines({ payrollRun: 7 }, 'tk');
    expect(apiFetch).toHaveBeenCalledWith('people/payslip-lines/?payroll_run=7', { token: 'tk' });
  });
});
