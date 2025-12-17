# SchoolCafe Menu Sync - Docker Setup

This Docker container automatically syncs school lunch menus from SchoolCafe to Google Calendar every Sunday at 6:00 AM CST.

## Prerequisites

1. Docker and Docker Compose installed
2. Google Cloud project with Calendar API enabled
3. OAuth 2.0 credentials (client_secret.json)

## Setup Instructions

### 1. Get Google Calendar API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the credentials JSON file
5. Save the file as `client_secret.json` in this directory

### 2. Create Required Directories

```bash
mkdir -p data logs
```

### 3. Configure Environment Variables (Optional)

Create a `.env` file in this directory:

```bash
# Google Calendar ID (default: "primary" for your main calendar)
LUNCH_GCAL_ID=your-calendar-id@group.calendar.google.com

# Run sync immediately on startup (useful for testing)
RUN_ON_STARTUP=false
```

To find your calendar ID:
1. Open Google Calendar
2. Click the three dots next to your calendar → "Settings and sharing"
3. Scroll down to "Integrate calendar" → Copy the "Calendar ID"

### 4. First-Time Authentication

On the first run, you'll need to authenticate with Google:

```bash
# Start container and run sync immediately
RUN_ON_STARTUP=true docker-compose up

# Follow the authentication URL in the logs
# After authentication, token.json will be saved to ./data/
```

Alternatively, authenticate locally first:

```bash
# Run locally to authenticate
python3 src/getMenus.py

# Move token to data directory
mv token.json data/
```

### 5. Start the Container

```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Check cron logs
docker-compose exec schoolcafe tail -f /var/log/cron.log
```

## Directory Structure

```
.
├── Dockerfile              # Container definition
├── docker-compose.yml      # Container orchestration
├── docker-entrypoint.sh    # Startup script
├── crontab                 # Cron schedule (Sunday 6am CST)
├── requirements.txt        # Python dependencies
├── src/
│   └── getMenus.py        # Main sync script
├── client_secret.json     # Google OAuth credentials (you provide)
├── data/
│   └── token.json         # OAuth token (auto-generated)
└── logs/
    └── cron.log           # Sync logs
```

## Usage

### Check Status

```bash
# Check if container is running
docker-compose ps

# View recent logs
docker-compose logs --tail=50
```

### Manual Sync

```bash
# Run sync manually
docker-compose exec schoolcafe python3 src/getMenus.py

# Or restart with RUN_ON_STARTUP
RUN_ON_STARTUP=true docker-compose up -d
```

### View Cron Schedule

```bash
docker-compose exec schoolcafe crontab -l
```

### Stop Container

```bash
# Stop container
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Troubleshooting

### Authentication Issues

If authentication fails:

1. Ensure `client_secret.json` is in the project root
2. Delete `data/token.json` and re-authenticate
3. Check that Calendar API is enabled in Google Cloud Console

### Cron Not Running

Check cron logs:

```bash
docker-compose exec schoolcafe tail -f /var/log/cron.log
```

Test cron manually:

```bash
docker-compose exec schoolcafe bash -c "cd /app && python3 src/getMenus.py"
```

### Timezone Issues

The container is set to `America/Chicago` (CST). To change:

1. Edit `docker-compose.yml` and update the `TZ` environment variable
2. Rebuild: `docker-compose up -d --build`

### View Container Logs

```bash
# All logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100
```

## Cron Schedule

The sync runs every Sunday at 6:00 AM CST:

```cron
0 6 * * 0 cd /app && python3 src/getMenus.py
```

To modify the schedule:
1. Edit `crontab` file
2. Rebuild: `docker-compose up -d --build`

Cron format: `minute hour day month weekday`
- `0 6 * * 0` = 6:00 AM on Sunday
- `0 6 * * 1` = 6:00 AM on Monday
- `0 18 * * *` = 6:00 PM every day

## Security Notes

- Keep `client_secret.json` secure and never commit to version control
- The `token.json` file contains access credentials - keep it secure
- Consider using a service account for production deployments
- The container runs as root by default - consider adding a non-root user for production

## Maintenance

### Update Dependencies

```bash
# Rebuild container with latest dependencies
docker-compose build --no-cache
docker-compose up -d
```

### Backup Token

```bash
# Backup token file
cp data/token.json data/token.json.backup
```

### View Calendar Events

Check your Google Calendar to verify events are being created with titles like:
- "School Lunch: Pizza"
- "School Lunch: Burger"

## Support

For issues:
1. Check container logs: `docker-compose logs`
2. Check cron logs: `docker-compose exec schoolcafe cat /var/log/cron.log`
3. Test script manually: `docker-compose exec schoolcafe python3 src/getMenus.py`

## Development vs Production

### Production (Default)
Code is baked into the image for portability and consistency:
```bash
# Requires rebuild when code changes
docker-compose up -d --build
```

### Development Mode
Source code is mounted as a volume - changes apply immediately without rebuild:
```bash
# Use dev compose file
docker-compose -f docker-compose.dev.yml up -d

# Code changes apply immediately - just restart container
docker-compose -f docker-compose.dev.yml restart
```

**When to use each:**
- **Production**: `docker-compose.yml` - Code baked in, more portable
- **Development**: `docker-compose.dev.yml` - Live code updates, no rebuild needed
