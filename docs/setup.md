# Cozy Discord Bot - Setup Guide

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Discord Bot Token(s)
- Make

### Commands Overview
```bash
make dev       # Deploy development
make prod      # Deploy production
make status    # Check containers status
make logs-dev  # View development logs
make logs-prod # View production logs
make stop-dev  # Stop development
make stop-prod # Stop production
```

---

## 📋 Initial Setup

### 1. Clone Repository
```bash
git clone https://github.com/kitsuiwebster/cozy-bot.git
cd cozy-bot
```

### 2. Create Environment Files

The new architecture uses separate `.env` files inside each environment directory:

```bash
# Configure development environment
nano dev/.env

# Configure production environment
nano prod/.env
```

### 3. Configure Environment Variables

#### `dev/.env` (Development)
```bash
COMPOSE_PROJECT_NAME=cozy-dev
DISCORD_BOT_TOKEN=your_development_token_here
API_KEY=your_api_key_here
BOT_MODE=dev
ENVIRONMENT=development
CONTAINER_NAME=cozy-discord-bot-dev
RESTART_POLICY=no
NETWORK_NAME=cozy-bot-network-dev
VOLUME_NAME=cozy-bot-logs-dev
VOICE_DATA_VOLUME=cozy-bot-voice-data-dev
API_PORT=8001
HEALTH_CHECK_DISABLE=true
DEV_CODE_MOUNT=.
```

#### `prod/.env` (Production)
```bash
COMPOSE_PROJECT_NAME=cozy-prod
DISCORD_BOT_TOKEN=your_production_token_here
API_KEY=your_api_key_here
BOT_MODE=prod
ENVIRONMENT=production
CONTAINER_NAME=cozy-discord-bot-prod
RESTART_POLICY=unless-stopped
NETWORK_NAME=cozy-bot-network-prod
VOLUME_NAME=cozy-bot-logs-prod
VOICE_DATA_VOLUME=cozy-bot-voice-data-prod
API_PORT=8000
HEALTH_CHECK_DISABLE=false
DEV_CODE_MOUNT=/tmp/empty
```

---

## 🛠️ Development

### Local Development
```bash
# Start development environment
make dev

# View logs in real-time
make logs-dev

# Stop when done
make stop-dev
```

### Development Features
- **Hot Reload**: Code changes automatically restart bot
- **Source Mounting**: Edit files locally, changes reflect immediately
- **No Health Checks**: Faster restarts during development
- **Separate Network**: Isolated from production
- **API Port**: 8001 (different from production)

### Development Workflow
1. Make changes in `dev/` directory
2. Changes are automatically reflected (hot reload)
3. Test your changes
4. Commit to `dev` branch when ready

---

## 🚀 Production

### Local Production Testing
```bash
# Start production environment
make prod

# Check health
make status

# View logs
make logs-prod
```

### Production Features
- **Health Checks**: Automatic container health monitoring
- **Auto Restart**: Container restarts on failure
- **Optimized**: Production-ready configuration
- **Security**: No source code mounting
- **API Port**: 8000 (default)

---

## 🌐 Server Deployment

### VPS Setup

The architecture allows both dev and prod to run simultaneously on the same server without conflicts:

```bash
# SSH to server
ssh user@your-server-ip

# Clone repository
git clone https://github.com/kitsuiwebster/cozy-bot.git
cd cozy-bot

# Configure environments
nano dev/.env   # Add development token & config
nano prod/.env  # Add production token & config

# Deploy both environments
make dev
make prod

# Check both are running
make status
```

### Benefits of Architecture
- ✅ **No Conflicts**: Dev and prod use separate directories and configs
- ✅ **Independent Data**: Each has its own `data/` and `logs/` directories
- ✅ **Different Ports**: API on 8001 (dev) and 8000 (prod)
- ✅ **Different Networks**: Fully isolated Docker networks
- ✅ **Easy Management**: Simple `make dev` or `make prod` commands

### Automatic Deployment (CI/CD)
- **Production**: Push to `main` branch → Auto-deploy to production
- **Development**: Push to `dev` branch → Auto-deploy to development

### Server Management Commands
```bash
# Check both environments
make status

# View logs
make logs-prod   # Production logs
make logs-dev    # Development logs

# Restart specific environment
make stop-dev && make dev
make stop-prod && make prod

# Clean up Docker resources
make clean
```

---

## 🔧 Configuration Details

### Environment Variables Explained

| Variable | Dev Value | Prod Value | Description |
|----------|-----------|------------|-------------|
| `COMPOSE_PROJECT_NAME` | `cozy-dev` | `cozy-prod` | Docker project isolation |
| `DISCORD_BOT_TOKEN` | Dev token | Prod token | Bot authentication |
| `API_KEY` | API key | API key | API authentication |
| `CONTAINER_NAME` | `*-dev` | `*-prod` | Container identification |
| `RESTART_POLICY` | `no` | `unless-stopped` | Auto-restart behavior |
| `API_PORT` | `8001` | `8000` | API server port |
| `HEALTH_CHECK_DISABLE` | `true` | `false` | Health monitoring |
| `DEV_CODE_MOUNT` | `.` | `/tmp/empty` | Source code mounting |

### Directory Structure

Each environment is self-contained:

```
dev/
├── .env                   # Dev configuration
├── main.py, server.py     # Bot code
├── cogs/, api/, utils/    # Source code
├── data/                  # Dev data (gitignored)
└── logs/                  # Dev logs (gitignored)

prod/
├── .env                   # Prod configuration
├── main.py, server.py     # Bot code
├── cogs/, api/, utils/    # Source code
├── data/                  # Prod data (gitignored)
└── logs/                  # Prod logs (gitignored)
```

---

## 🔍 Troubleshooting

### Container won't start
```bash
# Check logs for errors
make logs-dev   # or logs-prod

# Verify .env file exists
ls -la dev/.env prod/.env

# Check Docker status
docker ps -a
```

### Port conflicts
```bash
# Check if ports are in use
netstat -tulpn | grep 800

# Modify API_PORT in .env if needed
nano dev/.env    # Change API_PORT
nano prod/.env   # Change API_PORT
```

### Both environments conflict
```bash
# This shouldn't happen with new architecture
# But if it does, check:
make status

# Ensure different:
# - Container names
# - Network names
# - API ports
# - Volume names
```

---

## 📚 Additional Resources

- [Architecture Documentation](./architecture.md) - Detailed project structure
- [CozyPoints System](./cozypoints.md) - Gamification details
- [Development Article](./article.md) - Project journey and technical details

---

## 🆘 Support

Need help?
- Check the [GitHub Issues](https://github.com/kitsuiwebster/cozy-bot/issues)
- Read the [architecture documentation](./architecture.md)
- Contact the maintainers
