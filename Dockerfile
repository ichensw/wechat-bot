FROM python:3.11-slim AS base

LABEL maintainer="WeChatBot"
LABEL description="WeChatFerry-based WeChat monitoring bot v2.0"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose WebHook port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Non-root user for security
RUN useradd -r -s /bin/false wechatbot && chown -R wechatbot:wechatbot /app/data
USER wechatbot

# Default entry
CMD ["python3", "main.py", "-c", "config.yaml"]
