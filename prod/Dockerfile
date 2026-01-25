FROM python:3.11-slim

# Install system dependencies including ffmpeg and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install discord.py with voice v8 fix
RUN pip install discord.py[voice] --upgrade

# Copy the rest of the application
COPY . .

# Create a non-root user for security and create data directory
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    chown -R botuser:botuser /app

# Switch to the non-root user
USER botuser

# Default command (will be overridden by docker-compose)
CMD ["python3", "main.py"]
