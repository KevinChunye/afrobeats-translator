FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Don't run as root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Railway injects $PORT at runtime
ENV PORT=8000
EXPOSE 8000

CMD uvicorn web.app:app --host 0.0.0.0 --port $PORT
