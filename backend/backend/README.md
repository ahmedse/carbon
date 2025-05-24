# Backend

This folder contains the Django backend for the project.

## Structure

- **backend/**  
  Main project folder containing configuration and project-level files.
  - **settings.py**: Global Django settings, including installed apps, middleware, authentication, database, etc.
  - **urls.py**: Root URL routing for the project, includes routes for admin and app APIs.
  - **\_\_init\_\_.py**: Python package marker.
- **manage.py**  
  Command-line utility for running and managing the Django project.

## Getting Started

1. **Install dependencies**  
```bash
   pip install -r requirements.txt
```

2. **Set up environment variables**  
Create a .env file in the backend/ directory with required entries:
```ini
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5433
```

3. **Apply migrations** 
```bash
python manage.py migrate
```

4. **Run the development server** 
```bash
python manage.py runserver
```

**Notes**

All app-specific URLs are included under /api/ and /api/core/.
The project uses environment variables for sensitive settings.
Logging is configured to output DEBUG level logs to the console.

**Project Tree**
```
backend/
├── backend/
│   ├── __init__.py
│   ├── settings.py
│   └── urls.py
├── manage.py
└── ...
````