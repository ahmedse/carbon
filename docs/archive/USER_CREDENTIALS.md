# FIXED USER CREDENTIALS

**IMPORTANT: These credentials are FIXED and should NEVER be changed.**

## User Accounts

All users have access to the **AAST Carbon** project.

### 1. Administrator Account
- **Username:** `admin`
- **Password:** `admin123`
- **Email:** admin@aastmt.edu.eg
- **Role:** Admin (full system access)
- **Permissions:** All operations, user management, system configuration

### 2. Data Owner Account
- **Username:** `dataowner1`
- **Password:** `owner123`
- **Email:** dataowner1@aastmt.edu.eg
- **Role:** Data Owner
- **Permissions:** Create, read, update, delete data in assigned modules

### 3. Data Viewer Account
- **Username:** `dataviewer1`
- **Password:** `viewer123`
- **Email:** dataviewer1@aastmt.edu.eg
- **Role:** Data Viewer
- **Permissions:** Read-only access to data

## Setup Instructions

1. Run the user seeding script:
   ```bash
   cd /home/ahmed/carbon/backend
   python seed_users.py
   ```

2. Login at: `http://localhost:5173/carbon/login`

## Environment Configuration

All configuration is controlled by environment variables:

### Frontend (.env)
```
VITE_BASE=/carbon/
VITE_API_BASE_URL=http://localhost:8001/carbon-api/
VITE_API_TIMEOUT=30000
```

### Backend (.env)
```
DJANGO_ENV=development
SECRET_KEY=your-very-secret-key-change-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_API_PREFIX=/carbon-api/
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
DB_NAME=carbon_dev
DB_USER=carbon_user
DB_PASSWORD=securepassword123
DB_HOST=localhost
DB_PORT=5432
```

## Why These Are Fixed

1. **Consistency**: Same credentials across all environments and developers
2. **Documentation**: Easy to reference and share
3. **Testing**: Automated tests can use these credentials
4. **Development**: No confusion about login details
5. **Robustness**: No accidental changes that break authentication

## Security Note

**FOR DEVELOPMENT ONLY**
- These are development credentials
- For production, use secure, unique passwords
- Store production credentials in secure vaults (not in .env files)
- Use environment-specific configuration
