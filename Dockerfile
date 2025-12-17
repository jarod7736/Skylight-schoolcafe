FROM python:3.11-slim

# Install cron
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to CST
ENV TZ=America/Chicago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Copy entrypoint script
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

# Copy cron job file
COPY crontab /etc/cron.d/schoolcafe-cron
RUN chmod 0644 /etc/cron.d/schoolcafe-cron && \
    crontab /etc/cron.d/schoolcafe-cron

# Create log file
RUN touch /var/log/cron.log

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["cron", "-f"]
