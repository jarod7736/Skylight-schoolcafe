# Quick Start Guide

Get the SchoolCafe menu sync running in Docker in 5 minutes.

## 1. Prerequisites

- Docker and Docker Compose installed
- Google OAuth credentials (`client_secret.json`)

## 2. Setup

```bash
# Create required directories
mkdir -p data logs

# Copy your Google OAuth credentials
# (Download from Google Cloud Console if you don't have it)
cp /path/to/your/client_secret.json .
```

## 3. First Run (Authentication)

```bash
# Start container and run sync immediately
RUN_ON_STARTUP=true docker-compose up

# Or use make
RUN_ON_STARTUP=true make up
```

The first time, you'll see a URL in the logs. Open it to authenticate:
1. Open the URL in your browser
2. Sign in with Google
3. Grant calendar access
4. The token will be saved to `data/token.json`

## 4. Run Normally

```bash
# Start container in background
docker-compose up -d

# Or use make
make up
```

The sync will now run automatically every Sunday at 6:00 AM CST.

## 5. Verify

```bash
# Check logs
docker-compose logs

# Check cron logs
docker-compose exec schoolcafe tail /var/log/cron.log

# Run manual sync to test
docker-compose exec schoolcafe python3 src/getMenus.py
```

## Common Commands

```bash
# View logs
make logs

# View cron logs
make logs-cron

# Stop container
make down

# Rebuild
make build
```

## Troubleshooting

**"Not Found" or "Invalid resource id" errors?**
- Check your `LUNCH_GCAL_ID` in `.env` file
- Default is "primary" for your main calendar

**Token expired?**
```bash
# Delete token and re-authenticate
rm data/token.json
RUN_ON_STARTUP=true docker-compose up
```

**Need to change schedule?**
1. Edit `crontab` file
2. Rebuild: `docker-compose up -d --build`

For detailed documentation, see [DOCKER_README.md](DOCKER_README.md)
