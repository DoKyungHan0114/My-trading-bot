# Dockerfile for TQQQ Trading Bot
# Supports both trading bot and discord bot

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for logs and reports
RUN mkdir -p logs reports

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default: run trading bot in paper mode
# Override with: docker run ... python trading_bot.py --mode live
CMD ["python", "trading_bot.py", "--mode", "paper"]
