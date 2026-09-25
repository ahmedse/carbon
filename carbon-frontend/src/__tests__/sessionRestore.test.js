// src/__tests__/sessionRestore.test.js
import { describe, it, expect, beforeEach } from 'vitest';
import {
  ACTIVE_PLAN_KEY,
  ACTIVE_CONVERSATION_KEY,
  BOUND_USER_KEY,
  COPILOT_VISIBLE_KEY,
  LAST_PATH_KEY,
  WORKSPACE_BY_USER_KEY,
  applyWorkspaceForUser,
  clearAuthStorage,
  readActivePlanId,
  writeActivePlanId,
  clearActivePlanId,
  rememberLastPath,
  readLastPath,
  resolveLandingPath,
  isEphemeralPath,
} from '../shell/sessionRestore';

describe('sessionRestore — last Task plan', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('writes and reads the active plan id', () => {
    writeActivePlanId('plan-42');
    expect(localStorage.getItem(ACTIVE_PLAN_KEY)).toBe('plan-42');
    expect(readActivePlanId()).toBe('plan-42');
  });

  it('clears a stale plan pointer', () => {
    writeActivePlanId('plan-42');
    clearActivePlanId();
    expect(readActivePlanId()).toBeNull();
    expect(localStorage.getItem(ACTIVE_PLAN_KEY)).toBeNull();
  });
});

describe('sessionRestore — last brand route', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('remembers an in-app path with query', () => {
    rememberLastPath('/people/employees', '?q=ali');
    expect(readLastPath()).toBe('/people/employees?q=ali');
    expect(localStorage.getItem(LAST_PATH_KEY)).toBe('/people/employees?q=ali');
  });

  it('ignores auth paths', () => {
    rememberLastPath('/people/employees');
    rememberLastPath('/login');
    expect(readLastPath()).toBe('/people/employees');
    expect(isEphemeralPath('/login')).toBe(true);
    expect(isEphemeralPath('/forgot-password')).toBe(true);
  });

  it('resolveLandingPath prefers the remembered route', () => {
    rememberLastPath('/admin/groups');
    expect(resolveLandingPath('/dashboard')).toBe('/admin/groups');
  });

  it('resolveLandingPath falls back when nothing is stored', () => {
    expect(resolveLandingPath('/dashboard')).toBe('/dashboard');
    expect(resolveLandingPath()).toBe('/');
  });

  it('does not remember /dashboard (redirect alias) over a real page', () => {
    rememberLastPath('/people/employees');
    rememberLastPath('/dashboard');
    expect(isEphemeralPath('/dashboard')).toBe(true);
    expect(readLastPath()).toBe('/people/employees');
  });
});

describe('sessionRestore — workspace survives token wipe', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('clearAuthStorage drops tokens and keeps last path + Pulse pointers', () => {
    localStorage.setItem('user', JSON.stringify({ username: 'emp_2378' }));
    localStorage.setItem('access', 'tok');
    localStorage.setItem('refresh', 'ref');
    localStorage.setItem(LAST_PATH_KEY, '/people/payroll');
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, 'conv-pay');
    localStorage.setItem(COPILOT_VISIBLE_KEY, 'true');

    clearAuthStorage();

    expect(localStorage.getItem('access')).toBeNull();
    expect(localStorage.getItem('refresh')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
    expect(readLastPath()).toBe('/people/payroll');
    expect(localStorage.getItem(ACTIVE_CONVERSATION_KEY)).toBe('conv-pay');
    expect(localStorage.getItem(COPILOT_VISIBLE_KEY)).toBe('true');
    expect(localStorage.getItem(BOUND_USER_KEY)).toBe('emp_2378');
    expect(localStorage.getItem(WORKSPACE_BY_USER_KEY)).toBeTruthy();
  });

  it('applyWorkspaceForUser restores another operator without leaking Pulse', () => {
    localStorage.setItem('user', JSON.stringify({ username: 'emp_2378' }));
    localStorage.setItem(LAST_PATH_KEY, '/people/payroll');
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, 'conv-ali');
    applyWorkspaceForUser('emp_2378');

    applyWorkspaceForUser('emp_1067');
    expect(readLastPath()).toBeNull();
    expect(localStorage.getItem(ACTIVE_CONVERSATION_KEY)).toBeNull();

    localStorage.setItem(LAST_PATH_KEY, '/my/payslips');
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, 'conv-bilagot');
    applyWorkspaceForUser('emp_1067');

    applyWorkspaceForUser('emp_2378');
    expect(readLastPath()).toBe('/people/payroll');
    expect(localStorage.getItem(ACTIVE_CONVERSATION_KEY)).toBe('conv-ali');
  });
});
