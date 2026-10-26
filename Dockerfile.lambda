# ==============================================================================
# Fuel Check & Disha Voice Co-Pilot
# Single-Place Container for AWS Lambda (with AWS Lambda Web Adapter)
# Runs full Django backend + static frontend cockpit in one deployment
# ==============================================================================
FROM python:3.12-slim

# 1. Embed AWS Lambda Web Adapter (LWA)
# Converts AWS Lambda & Function URL invocations into standard HTTP on port 8000
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/api/health/ \
    IS_LAMBDA=true

WORKDIR /var/task

# 2. Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy application code, database, and frontend assets
COPY . .

# 4. Expose HTTP port
EXPOSE 8000

# 5. Start Gunicorn (1 worker + 4 threads optimized for Lambda memory)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "120", "config.wsgi:application"]
