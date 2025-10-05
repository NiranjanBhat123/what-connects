# Base stage
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Development stage
FROM base as development

# Copy requirements
COPY backend/requirements /app/requirements

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/development.txt

# Copy project
COPY backend /app

# Create user for running the app
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Production stage
FROM base as production

# Copy requirements
COPY backend/requirements /app/requirements

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/production.txt

# Copy project
COPY backend /app

# Create user for running the app
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4"]