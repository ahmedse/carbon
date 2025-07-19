# -- Build a production Django container with Gunicorn --

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create a user for security
RUN addgroup --system app && adduser --system --ingroup app app

# Install system dependencies, including sudo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    sudo \
    vim nano netcat iputils-ping git less \
    && echo 'app ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
    && pip install --upgrade pip



# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./

#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y libgomp1

# Clean up build dependencies
#RUN apt-get remove -y build-essential && \
 #   apt-get autoremove -y && \
  #  apt-get clean && \
   # rm -rf /var/lib/apt/lists/*

# Copy app files and set permissions
COPY . .
RUN mkdir -p /static /media && chown -R app:app /app /static /media


# Switch to non-root user with sudo privileges
USER app

# Start Gunicorn server
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
