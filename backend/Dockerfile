# File: Dockerfile
# Purpose: Docker configuration for building and running the Django application.
# Location: (project root)
#
# This Dockerfile sets up a Python 3.10 environment, installs dependencies,
# and runs the Django application using the development server on port 8000.
# For production, consider using a WSGI server like gunicorn.

FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency list
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the container
COPY . .

# Ensure stdout/stderr are unbuffered (useful for logging)
ENV PYTHONUNBUFFERED=1

# Expose Django's default port
EXPOSE 8000

# Start the Django development server (not recommended for production)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]