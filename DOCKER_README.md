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

# SchoolCafe school/district identifiers (defaults shown below)
SCHOOLCAFE_SCHOOL_ID=10de21a6-64e7-4bd0-9d8c-8a17d2cfe022
SCHOOLCAFE_DISTRICT_ID=400
SCHOOLCAFE_GRADE=08
SCHOOLCAFE_SERVING_LINE=Lunch
SCHOOLCAFE_MEAL_TYPE=Lunch
```

To find your calendar ID:
1. Open Google Calendar
2. Click the three dots next to your calendar → "Settings and sharing"
3. Scroll down to "Integrate calendar" → Copy the "Calendar ID"

### 4. First-Time Authentication

**First-time auth must be done on a machine with a browser — Docker has no browser.**

```bash
# On your local machine (not inside Docker):
python3 src/getMenus.py
```

A browser window will open for Google OAuth. After you approve access, a `token.json`
file is written in the current directory. Copy it into the `data/` directory:

```bash
cp token.json data/
```

Once `data/token.json` exists with a `refresh_token`, the container will silently
refresh credentials on every subsequent run without any browser interaction. You
should never need to repeat this step unless you revoke the token in Google Account
settings or delete `data/token.json`.

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

## CI/CD: Automated Docker Builds

The Docker image is automatically built and pushed to GitHub Container Registry (ghcr.io) on every push to `main`.

### Image Location

```
ghcr.io/jarod7736/skylight-schoolcafe:latest
ghcr.io/jarod7736/skylight-schoolcafe:<git-sha>  # pinned version tag
```

### Pulling the Latest Image (Synology / Remote Hosts)

`docker-compose.yml` is pre-configured to pull from ghcr.io. To update to the latest image:

```bash
docker-compose pull
docker-compose up -d
```

No rebuild is required — the image is pre-built in CI.

### Local Development Build

To build the image locally instead of pulling from the registry, edit `docker-compose.yml` and swap the `image` / `build` lines:

```yaml
services:
  schoolcafe:
    # image: ghcr.io/jarod7736/skylight-schoolcafe:latest
    build: .
```

Or use the dev compose file, which mounts source code for live editing without rebuilds:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Development vs Production

### Production (Default)
Pulls the pre-built image from ghcr.io — no local build required:
```bash
docker-compose pull && docker-compose up -d
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
- **Production / Synology**: `docker-compose.yml` - Pulls from ghcr.io, no build needed
- **Development**: `docker-compose.dev.yml` - Live code updates, no rebuild needed
