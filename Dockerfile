# Blind Analytics — Dockerfile for Railway / container deploys
# Stage B: Streamlit + Playwright headless Chromium

FROM python:3.12-slim

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libx11-xcb1 \
    libxcb-dri3-0 libxfixes3 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser binaries (build-time, not runtime)
RUN playwright install chromium

# Copy application code
COPY . .

# Streamlit config
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s \
    CMD curl -f http://localhost:8080/_stcore/health || exit 1

CMD ["streamlit", "run", "src/streamlit/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
