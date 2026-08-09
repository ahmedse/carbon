# ── Carbon Data Trust Platform — Production Dockerfile ──────────────
#  Builds a secure Django container with Gunicorn.
#  Dev tools (vim, nano, etc.) are NOT included.
#  Build dependencies are cleaned up after pip install.
# ────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create a non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

# Install ONLY what's needed at runtime: libpq for psycopg2, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    libgomp1 \
    && pip install --upgrade pip

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Clean up build dependencies — NOT left in the image
RUN apt-get remove -y build-essential && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy app files
COPY . .

# Create volume mount points and set ownership
RUN mkdir -p /static /media /app/dataschema_uploads \
    && chown -R app:app /app /static /media

# Set MPLCONFIGDIR to suppress matplotlib warnings
ENV MPLCONFIGDIR=/tmp

# Copy entrypoint (migrations + collectstatic + gunicorn)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER app

ENTRYPOINT ["/app/entrypoint.sh"]
