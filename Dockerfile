FROM python:3.11-slim

# Build-time deps for compiled Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first — separate layer so Docker caches it
# unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium AND all its system dependencies in one command.
# This layer is ~350MB but only rebuilds when requirements.txt changes.
RUN playwright install --with-deps chromium

# Copy application source code
COPY . .

# Create data directory (overridden by volume mount in production)
RUN mkdir -p /data/outputs /app/outputs

EXPOSE 8501

ENV PYTHONUNBUFFERED=1

# Uses ${PORT:-8501} so Railway/Render/Fly can inject $PORT at runtime
CMD sh -c "streamlit run app/Home.py \
  --server.port=${PORT:-8501} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.fileWatcherType=none"
