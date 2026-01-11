# API Testing & Quality Assurance Guide

This document provides a comprehensive testing strategy for the Carbon platform.

---

## CURRENT STATE

**Test Coverage:** ~10-15% (estimated)  
**Status:** ❌ **Critical Gap** - Production deployment blocked

### Existing Tests
- ✅ `backend/accounts/tests/test_auth.py` - Basic auth tests
- ✅ `backend/accounts/tests/test_security.py` - Security tests
- ❌ No tests for Core models
- ❌ No tests for DataSchema models
- ❌ No frontend tests

---

## TESTING PYRAMID STRATEGY

```
        /\
       /E2E\      5% - End-to-End (Critical User Flows)
      /----\
     /Integ-\     15% - Integration (API + DB)
    /--------\
   /Unit Tests\   80% - Unit (Functions, Models, Components)
  /__________\
```

### Target Metrics

| Category | Current | Target | Priority |
|----------|---------|--------|----------|
| Backend Coverage | 15% | 80% | 🔴 Critical |
| Frontend Coverage | 0% | 70% | 🔴 Critical |
| E2E Coverage | 0% | 5 flows | 🟡 High |
| API Tests | Minimal | Comprehensive | 🔴 Critical |

---

## 1. BACKEND TESTING STRATEGY

### Setup

**Install Dependencies:**
```bash
cd backend
pip install pytest pytest-django pytest-cov factory-boy freezegun faker
pip freeze > requirements.txt
```

**Configure pytest:** `backend/pytest.ini`
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = 
    --cov=.
    --cov-report=html:htmlcov
    --cov-report=term-missing:skip-covered
    --cov-branch
    --verbose
    --strict-markers
    --tb=short
    --disable-warnings
testpaths = .
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### Test Structure

```
backend/
  conftest.py                      # Global fixtures
  accounts/
    tests/
      __init__.py
      conftest.py                  # App-specific fixtures
      test_models.py               # Tenant, User, ScopedRole tests
      test_views.py                # API endpoint tests
      test_permissions.py          # RBAC tests
      test_serializers.py          # Serialization tests
      test_rbac_utils.py           # Helper function tests
      test_auth.py ✅              # Existing
      test_security.py ✅          # Existing
  core/
    tests/
      test_models.py               # Project, Module, Cycle tests
      test_views.py                # Project/Module CRUD tests
      test_permissions.py          # Project access control
  dataschema/
    tests/
      test_models.py               # DataTable, DataField, DataRow
      test_views.py                # Dynamic schema CRUD
      test_validation.py           # Field type validation
      test_csv_import.py           # CSV import logic
```

### Fixtures

**File:** `backend/conftest.py`

```python
import pytest
from django.contrib.auth.models import Group
from accounts.models import User, Tenant, ScopedRole
from core.models import Project, Module
from dataschema.models import DataTable, DataField

# ========== DATABASE SETUP ==========

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Create default groups once for entire test session."""
    with django_db_blocker.unblock():
        Group.objects.get_or_create(name='admins_group')
        Group.objects.get_or_create(name='dataowners_group')
        Group.objects.get_or_create(name='auditors_group')

# ========== TENANT FIXTURES ==========

@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        is_active=True
    )

@pytest.fixture
def tenant_b(db):
    """Second tenant for isolation tests."""
    return Tenant.objects.create(
        name="Tenant B",
        slug="tenant-b",
        is_active=True
    )

# ========== USER FIXTURES ==========

@pytest.fixture
def admin_user(db, tenant):
    """Admin user with full permissions."""
    user = User.objects.create_user(
        email="admin@test.com",
        password="Admin123!",
        first_name="Admin",
        last_name="User",
        tenant=tenant,
        is_staff=True
    )
    admin_group = Group.objects.get(name='admins_group')
    ScopedRole.objects.create(
        user=user,
        group=admin_group,
        tenant=tenant
    )
    return user

@pytest.fixture
def dataowner_user(db, tenant):
    """Data owner user (limited permissions)."""
    user = User.objects.create_user(
        email="dataowner@test.com",
        password="DataOwner123!",
        first_name="Data",
        last_name="Owner",
        tenant=tenant
    )
    return user

@pytest.fixture
def auditor_user(db, tenant):
    """Auditor user (read-only)."""
    user = User.objects.create_user(
        email="auditor@test.com",
        password="Auditor123!",
        tenant=tenant
    )
    auditor_group = Group.objects.get(name='auditors_group')
    ScopedRole.objects.create(
        user=user,
        group=auditor_group,
        tenant=tenant
    )
    return user

# ========== PROJECT FIXTURES ==========

@pytest.fixture
def project(db, tenant, admin_user):
    """Create a test project."""
    return Project.objects.create(
        name="Test Project",
        description="Test project description",
        tenant=tenant,
        created_by=admin_user
    )

@pytest.fixture
def project_b(db, tenant_b, admin_user):
    """Project in different tenant for isolation tests."""
    other_admin = User.objects.create_user(
        email="admin_b@test.com",
        password="Admin123!",
        tenant=tenant_b,
        is_staff=True
    )
    return Project.objects.create(
        name="Project B",
        tenant=tenant_b,
        created_by=other_admin
    )

# ========== MODULE FIXTURES ==========

@pytest.fixture
def module_scope1(db, project, admin_user):
    """Scope 1 module (Direct Emissions)."""
    return Module.objects.create(
        name="Stationary Combustion",
        description="Fossil fuels burned on-site",
        scope=1,
        project=project,
        created_by=admin_user
    )

@pytest.fixture
def module_scope2(db, project, admin_user):
    """Scope 2 module (Indirect Emissions)."""
    return Module.objects.create(
        name="Purchased Electricity",
        scope=2,
        project=project,
        created_by=admin_user
    )

# ========== DATATABLE FIXTURES ==========

@pytest.fixture
def data_table(db, module_scope1, admin_user):
    """Create a data table with fields."""
    table = DataTable.objects.create(
        name="Fuel Consumption",
        description="Track fuel usage",
        module=module_scope1,
        created_by=admin_user
    )
    
    # Add fields
    DataField.objects.create(
        table=table,
        name="date",
        label="Date",
        field_type="date",
        is_required=True,
        order=1
    )
    DataField.objects.create(
        table=table,
        name="fuel_type",
        label="Fuel Type",
        field_type="select",
        is_required=True,
        options={'choices': ['Diesel', 'Gasoline', 'Natural Gas']},
        order=2
    )
    DataField.objects.create(
        table=table,
        name="quantity",
        label="Quantity (liters)",
        field_type="number",
        is_required=True,
        validation={'min': 0},
        order=3
    )
    
    return table

# ========== API CLIENT FIXTURES ==========

@pytest.fixture
def api_client():
    """DRF API client for testing."""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def authenticated_client(api_client, admin_user):
    """API client authenticated as admin."""
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def dataowner_client(api_client, dataowner_user):
    """API client authenticated as data owner."""
    api_client.force_authenticate(user=dataowner_user)
    return api_client
```

### Example Tests

**File:** `backend/accounts/tests/test_permissions.py`

```python
import pytest
from accounts.permissions import HasScopedRole
from accounts.rbac_utils import get_allowed_project_ids
from accounts.models import ScopedRole
from django.contrib.auth.models import Group

@pytest.mark.django_db
class TestRBACPermissions:
    """Test Role-Based Access Control."""
    
    def test_admin_sees_all_projects_in_tenant(self, admin_user, project, tenant):
        """Admin should see all projects in their tenant."""
        allowed_ids = get_allowed_project_ids(admin_user)
        assert project.id in allowed_ids
    
    def test_dataowner_sees_only_assigned_projects(self, dataowner_user, project):
        """Data owner should only see projects they're assigned to."""
        # Initially no access
        allowed_ids = get_allowed_project_ids(dataowner_user)
        assert project.id not in allowed_ids
        
        # Assign to project
        group = Group.objects.get(name='dataowners_group')
        ScopedRole.objects.create(
            user=dataowner_user,
            group=group,
            project=project
        )
        
        # Now has access
        allowed_ids = get_allowed_project_ids(dataowner_user)
        assert project.id in allowed_ids
    
    def test_tenant_isolation(self, admin_user, project_b):
        """Users cannot see projects from other tenants."""
        allowed_ids = get_allowed_project_ids(admin_user)
        assert project_b.id not in allowed_ids
    
    def test_auditor_has_read_only_access(self, auditor_user, project):
        """Auditors can view but not edit."""
        # Assign auditor to project
        auditor_group = Group.objects.get(name='auditors_group')
        ScopedRole.objects.create(
            user=auditor_user,
            group=auditor_group,
            project=project
        )
        
        # Can see project
        allowed_ids = get_allowed_project_ids(auditor_user)
        assert project.id in allowed_ids
```

**File:** `backend/core/tests/test_views.py`

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestProjectViewSet:
    """Test Project API endpoints."""
    
    def test_list_projects_authenticated(self, authenticated_client, project):
        """Authenticated users can list their projects."""
        url = reverse('project-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert len(response.data) >= 1
        assert any(p['id'] == project.id for p in response.data)
    
    def test_list_projects_unauthenticated(self, api_client, project):
        """Unauthenticated users cannot list projects."""
        url = reverse('project-list')
        response = api_client.get(url)
        
        assert response.status_code == 401
    
    def test_create_project_as_admin(self, authenticated_client, tenant):
        """Admin can create new projects."""
        url = reverse('project-list')
        data = {
            'name': 'New Project',
            'description': 'Test description'
        }
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 201
        assert response.data['name'] == 'New Project'
    
    def test_create_project_as_dataowner_denied(self, dataowner_client):
        """Data owners cannot create projects."""
        url = reverse('project-list')
        data = {'name': 'Should Fail'}
        response = dataowner_client.post(url, data)
        
        assert response.status_code == 403
    
    def test_project_name_unique_per_tenant(self, authenticated_client, project):
        """Cannot create duplicate project names in same tenant."""
        url = reverse('project-list')
        data = {'name': project.name}  # Duplicate name
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 400
```

**File:** `backend/dataschema/tests/test_models.py`

```python
import pytest
from dataschema.models import DataRow, DataField

@pytest.mark.django_db
class TestDataRow:
    """Test DataRow model and validation."""
    
    def test_create_row_with_valid_data(self, data_table, admin_user):
        """Can create row with valid field values."""
        row = DataRow.objects.create(
            table=data_table,
            values={
                'date': '2024-01-15',
                'fuel_type': 'Diesel',
                'quantity': 500.5
            },
            created_by=admin_user
        )
        
        assert row.id is not None
        assert row.values['fuel_type'] == 'Diesel'
    
    def test_required_field_validation(self, data_table, admin_user):
        """Missing required field raises validation error."""
        with pytest.raises(ValidationError):
            row = DataRow(
                table=data_table,
                values={'date': '2024-01-15'},  # Missing fuel_type and quantity
                created_by=admin_user
            )
            row.full_clean()
    
    def test_number_field_type_validation(self, data_table, admin_user):
        """Non-numeric value in number field raises error."""
        with pytest.raises(ValidationError):
            row = DataRow(
                table=data_table,
                values={
                    'date': '2024-01-15',
                    'fuel_type': 'Diesel',
                    'quantity': 'not-a-number'  # Invalid
                },
                created_by=admin_user
            )
            row.full_clean()
```

### Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage report
pytest --cov

# Run specific app tests
pytest accounts/tests/

# Run specific test file
pytest accounts/tests/test_permissions.py

# Run specific test
pytest accounts/tests/test_permissions.py::TestRBACPermissions::test_admin_sees_all_projects_in_tenant

# Run and stop on first failure
pytest -x

# Run only fast tests (exclude slow)
pytest -m "not slow"

# Generate HTML coverage report
pytest --cov --cov-report=html
# Open htmlcov/index.html in browser
```

---

## 2. FRONTEND TESTING STRATEGY

### Setup

**Install Dependencies:**
```bash
cd carbon-frontend
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw
```

**Configure Vitest:** `carbon-frontend/vitest.config.js`

```javascript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/tests/',
        '**/*.spec.jsx',
        '**/*.test.jsx',
      ],
    },
  },
});
```

**Setup File:** `carbon-frontend/src/tests/setup.js`

```javascript
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Extend Vitest matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
});
```

**Update package.json:**
```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage"
  }
}
```

### Test Structure

```
carbon-frontend/
  src/
    tests/
      setup.js
      mocks/
        handlers.js          # MSW API mocks
        server.js            # Mock server setup
    auth/
      __tests__/
        AuthContext.test.jsx
    components/
      __tests__/
        DataEntryForm.test.jsx
        ModuleCard.test.jsx
    pages/
      __tests__/
        Login.test.jsx
        Dashboard.test.jsx
        TableManagerPage.test.jsx
```

### Example Tests

**File:** `carbon-frontend/src/tests/mocks/handlers.js`

```javascript
import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8001/carbon-api';

export const handlers = [
  // Auth endpoints
  http.post(`${API_URL}/token/`, () => {
    return HttpResponse.json({
      access: 'fake-access-token',
      refresh: 'fake-refresh-token',
    });
  }),
  
  http.get(`${API_URL}/accounts/my-roles/`, () => {
    return HttpResponse.json({
      roles: [
        {
          id: 1,
          user_email: 'test@example.com',
          group_name: 'admins_group',
          project_id: 1,
          project_name: 'Test Project',
        },
      ],
    });
  }),
  
  // Projects endpoint
  http.get(`${API_URL}/core/projects/`, () => {
    return HttpResponse.json([
      {
        id: 1,
        name: 'Test Project',
        description: 'Test description',
        tenant: 1,
      },
    ]);
  }),
];
```

**File:** `carbon-frontend/src/tests/mocks/server.js`

```javascript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

**File:** `carbon-frontend/src/pages/__tests__/Login.test.jsx`

```javascript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { server } from '../../tests/mocks/server';
import Login from '../Login';
import { AuthProvider } from '../../auth/AuthContext';

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Login Page', () => {
  const renderLogin = () => {
    return render(
      <BrowserRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </BrowserRouter>
    );
  };
  
  it('renders login form', () => {
    renderLogin();
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });
  
  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup();
    renderLogin();
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitButton);
    
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
  });
  
  it('submits login form with valid credentials', async () => {
    const user = userEvent.setup();
    renderLogin();
    
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    
    await waitFor(() => {
      // Check if token is stored or navigation occurred
      expect(localStorage.getItem('accessToken')).toBeTruthy();
    });
  });
  
  it('displays error message on failed login', async () => {
    const user = userEvent.setup();
    
    // Override handler to return error
    server.use(
      http.post('http://localhost:8001/carbon-api/token/', () => {
        return HttpResponse.json(
          { detail: 'Invalid credentials' },
          { status: 401 }
        );
      })
    );
    
    renderLogin();
    
    await user.type(screen.getByLabelText(/email/i), 'wrong@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    
    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });
});
```

**File:** `carbon-frontend/src/auth/__tests__/AuthContext.test.jsx`

```javascript
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { server } from '../../tests/mocks/server';
import { AuthProvider, useAuth } from '../AuthContext';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('AuthContext', () => {
  it('provides auth state', () => {
    const wrapper = ({ children }) => <AuthProvider>{children}</AuthProvider>;
    const { result } = renderHook(() => useAuth(), { wrapper });
    
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
  
  it('logs in user and sets tokens', async () => {
    const wrapper = ({ children }) => <AuthProvider>{children}</AuthProvider>;
    const { result } = renderHook(() => useAuth(), { wrapper });
    
    await result.current.login('test@example.com', 'password123');
    
    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
      expect(localStorage.getItem('accessToken')).toBeTruthy();
    });
  });
  
  it('logs out user and clears tokens', async () => {
    const wrapper = ({ children }) => <AuthProvider>{children}</AuthProvider>;
    const { result } = renderHook(() => useAuth(), { wrapper });
    
    // Login first
    await result.current.login('test@example.com', 'password123');
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    
    // Logout
    result.current.logout();
    
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem('accessToken')).toBeNull();
  });
});
```

### Running Frontend Tests

```bash
cd carbon-frontend

# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui
```

---

## 3. END-TO-END TESTING

### Setup Playwright

```bash
cd carbon-frontend
npm install --save-dev @playwright/test
npx playwright install
```

**Configure:** `carbon-frontend/playwright.config.js`

```javascript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

### Example E2E Test

**File:** `carbon-frontend/e2e/login-flow.spec.js`

```javascript
import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test('user can log in and see dashboard', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');
    
    // Fill login form
    await page.fill('input[name="email"]', 'admin@test.com');
    await page.fill('input[name="password"]', 'Admin123!');
    
    // Click submit
    await page.click('button[type="submit"]');
    
    // Wait for navigation to dashboard
    await page.waitForURL('/dashboard');
    
    // Verify dashboard loaded
    await expect(page.locator('h4')).toContainText('Dashboard');
  });
  
  test('invalid credentials show error', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('input[name="email"]', 'wrong@test.com');
    await page.fill('input[name="password"]', 'wrongpass');
    await page.click('button[type="submit"]');
    
    // Error message should appear
    await expect(page.locator('[role="alert"]')).toContainText('Invalid');
  });
});

test.describe('Data Entry Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="email"]', 'dataowner@test.com');
    await page.fill('input[name="password"]', 'DataOwner123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });
  
  test('user can create data row', async ({ page }) => {
    // Navigate to module
    await page.click('text=Stationary Combustion');
    
    // Navigate to table
    await page.click('text=Fuel Consumption');
    
    // Click add row button
    await page.click('button:has-text("Add Row")');
    
    // Fill form
    await page.fill('input[name="date"]', '2024-01-15');
    await page.selectOption('select[name="fuel_type"]', 'Diesel');
    await page.fill('input[name="quantity"]', '500');
    
    // Submit
    await page.click('button:has-text("Save")');
    
    // Verify success message
    await expect(page.locator('[role="alert"]')).toContainText('Success');
  });
});
```

### Run E2E Tests

```bash
cd carbon-frontend

# Run all E2E tests
npx playwright test

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific test
npx playwright test e2e/login-flow.spec.js

# Show report
npx playwright show-report
```

---

## 4. CONTINUOUS INTEGRATION

### GitHub Actions Workflow

**File:** `.github/workflows/test.yml`

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_carbon_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        working-directory: ./backend
        run: |
          pip install -r requirements.txt
      
      - name: Run migrations
        working-directory: ./backend
        env:
          DB_HOST: localhost
          DB_PORT: 5432
          DB_NAME: test_carbon_db
          DB_USER: test_user
          DB_PASSWORD: test_password
        run: |
          python manage.py migrate
      
      - name: Run tests with coverage
        working-directory: ./backend
        run: |
          pytest --cov --cov-report=xml --cov-report=term
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
          flags: backend
  
  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: carbon-frontend/package-lock.json
      
      - name: Install dependencies
        working-directory: ./carbon-frontend
        run: npm ci
      
      - name: Run tests with coverage
        working-directory: ./carbon-frontend
        run: npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./carbon-frontend/coverage/coverage-final.json
          flags: frontend
  
  e2e-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_carbon_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python & Node
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install Python dependencies
        working-directory: ./backend
        run: pip install -r requirements.txt
      
      - name: Install Node dependencies
        working-directory: ./carbon-frontend
        run: npm ci
      
      - name: Run migrations
        working-directory: ./backend
        run: python manage.py migrate
      
      - name: Start backend server
        working-directory: ./backend
        run: |
          python manage.py runserver 8001 &
          sleep 5
      
      - name: Install Playwright
        working-directory: ./carbon-frontend
        run: npx playwright install --with-deps
      
      - name: Run E2E tests
        working-directory: ./carbon-frontend
        run: npx playwright test
      
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: carbon-frontend/playwright-report/
```

---

## 5. TESTING CHECKLIST

### Before Production Deployment

**Backend:**
- [ ] 80%+ test coverage
- [ ] All RBAC permission tests passing
- [ ] Tenant isolation tests passing
- [ ] API endpoint tests for all CRUD operations
- [ ] CSV import validation tests
- [ ] Field validation tests
- [ ] Security tests (SQL injection, XSS, etc.)

**Frontend:**
- [ ] 70%+ test coverage
- [ ] Login/logout flow tested
- [ ] Project selection tested
- [ ] Data entry form validation tested
- [ ] Error handling tested
- [ ] Loading states tested

**E2E:**
- [ ] Critical user journeys tested
- [ ] Admin workflow tested
- [ ] Data owner workflow tested
- [ ] Auditor workflow tested

**Performance:**
- [ ] Load testing completed (1000+ concurrent users)
- [ ] Database query optimization verified
- [ ] API response times < 200ms (p95)

**Security:**
- [ ] OWASP Top 10 vulnerabilities checked
- [ ] Authentication/authorization tested
- [ ] Rate limiting verified
- [ ] CSRF protection enabled

---

## NEXT STEPS

1. **Immediate (Week 1):**
   - Set up pytest and write RBAC tests
   - Set up Vitest and write Login component tests
   - Configure CI/CD pipeline

2. **Short-term (Weeks 2-4):**
   - Achieve 50%+ backend coverage
   - Achieve 40%+ frontend coverage
   - Write 3 critical E2E tests

3. **Medium-term (Weeks 5-8):**
   - Achieve 80% backend coverage
   - Achieve 70% frontend coverage
   - Set up performance testing

**Estimated Effort:** 6-8 weeks (2 developers part-time)

---

**Document Status:** ✅ Complete  
**Last Updated:** 2026-01-11
