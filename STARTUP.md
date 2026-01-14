# Vocard Startup Scripts

This project includes automated startup scripts that ensure Lavalink is running before starting the Discord bot.

## Quick Start

### Option 1: Python Script (Recommended)

```bash
python3 start.py
```

or

```bash
./start.py
```

### Option 2: Bash Script

```bash
bash start.sh
```

or

```bash
./start.sh
```

## What These Scripts Do

1. **Check Dependencies** - Verifies that Python dependencies are installed
2. **Check Lavalink Status** - Detects if Lavalink is already running on port 2333
3. **Start Lavalink** - If not running, starts Lavalink using Docker Compose
4. **Wait for Ready** - Waits up to 120 seconds for Lavalink to be healthy
5. **Start Bot** - Launches the Vocard Discord bot (`main.py`)

## Features

- ✅ Automatic Lavalink detection and startup
- ✅ Health checks to ensure Lavalink is ready
- ✅ Colored terminal output for better readability
- ✅ Error handling and clear error messages
- ✅ Optional dependency installation prompt
- ✅ Works with both Docker and manual Lavalink installations

## Requirements

### For Docker Method (Automatic)
- Docker and Docker Compose installed
- `docker-compose.yml` configured in the project root

### For Manual Method
- Lavalink running on `localhost:2333`
- Password: `youshallnotpass` (or update in scripts if changed)

## Configuration

You can modify these variables at the top of the scripts if your setup is different:

**Python (`start.py`):**
```python
LAVALINK_HOST = "localhost"
LAVALINK_PORT = 2333
LAVALINK_PASSWORD = "youshallnotpass"
MAX_WAIT_TIME = 120  # seconds
```

**Bash (`start.sh`):**
```bash
LAVALINK_HOST="localhost"
LAVALINK_PORT=2333
LAVALINK_PASSWORD="youshallnotpass"
MAX_WAIT_TIME=120
```

## Manual Installation

If you prefer to run everything manually:

### 1. Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 2. Start Lavalink

**Option A: Docker Compose**
```bash
docker compose up lavalink
```

**Option B: Standalone Java**
```bash
java -jar Lavalink.jar
```

### 3. Start the Bot

```bash
python3 main.py
```

## Troubleshooting

### "Lavalink did not become ready"

- Check Docker logs: `docker compose logs lavalink`
- Ensure port 2333 is not blocked by firewall
- Verify `lavalink/application.yml` configuration

### "Dependencies might be missing"

Run the installation command:
```bash
python3 -m pip install -r requirements.txt
```

### "Docker not found"

Install Docker:
- **macOS**: [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- **Linux**: Follow your distribution's Docker installation guide
- **Windows**: [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)

### Port Already in Use

If port 2333 is already in use by another application:
1. Check what's using it: `lsof -i :2333` (macOS/Linux)
2. Stop that application or change Lavalink's port in `application.yml`
3. Update the port in the startup scripts

## Additional Resources

- [Vocard Setup Documentation](https://docs.vocard.xyz/2.7.2/bot/setup/)
- [Lavalink Documentation](https://lavalink.dev/)
- [Docker Documentation](https://docs.docker.com/)

## Support

For issues with the startup scripts, check:
- Lavalink logs: `docker compose logs lavalink`
- Bot logs: Check console output or log files
- Project issues: [GitHub Issues](https://github.com/ChocoMeow/Vocard/issues)
