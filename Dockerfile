FROM python:3.11-slim

# System deps for Playwright Chromium + CJK fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxcomposite1 libxrandr2 libxdamage1 libxfixes3 \
    libgbm1 libasound2 libpangocairo-1.0-0 libgtk-3-0 \
    libx11-xcb1 libxcb-dri3-0 libdrm2 \
    wget ca-certificates fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium --with-deps

# Copy application source
COPY *.py ./
COPY .env.example ./

# Logs directory
RUN mkdir -p /app/logs

# Zeabur / Docker entry point
CMD ["python", "startup.py"]
