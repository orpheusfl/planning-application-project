FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Health check for ECS
HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Ensure environment variables are set for database connection
ENV DB_HOST="" \
    DB_PORT="5432" \
    DB_NAME="" \
    DB_USER="" \
    DB_PASSWORD="" \
    DB_SSL_CERT="./global-bundle.pem"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
