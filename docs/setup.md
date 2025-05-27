# Cozy Discord Bot

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Discord Bot Token(s)
- Make

### Commands Overview
```bash
make prod      # Deploy production
make dev       # Deploy development  
make status    # Check containers status
make logs-prod # View production logs
make logs-dev  # View development logs
make stop-prod # Stop production
make stop-dev  # Stop development
```

---

## 📋 Setup

### 1. Clone Repository
```bash
git clone https://github.com/kitsuiwebster/cozy-bot.git
cd cozy-discord-bot
```

### 2. Create Environment Files
```bash
# Configure with your tokens
nano .env.prod
nano .env.dev
```

### 3. Configure Environment Variables

#### `.env.prod` (Production)
```bash
COMPOSE_PROJECT_NAME=cozy-prod
DISCORD_BOT_TOKEN=your_production_token_here
BOT_MODE=prod
ENVIRONMENT=production
CONTAINER_NAME=cozy-discord-bot-prod
RESTART_POLICY=unless-stopped
NETWORK_NAME=cozy-bot-network-prod
VOLUME_NAME=cozy-bot-logs-prod
HEALTH_CHECK_DISABLE=false
DEV_CODE_MOUNT=/tmp/empty
BOT_COMMAND="python3 main.py"
```

#### `.env.dev` (Development)
```bash
COMPOSE_PROJECT_NAME=cozy-dev
DISCORD_BOT_TOKEN=your_development_token_here
BOT_MODE=dev
ENVIRONMENT=development
CONTAINER_NAME=cozy-discord-bot-dev
RESTART_POLICY=no
NETWORK_NAME=cozy-bot-network-dev
VOLUME_NAME=cozy-bot-logs-dev
HEALTH_CHECK_DISABLE=true
DEV_CODE_MOUNT=.
BOT_COMMAND="python3 main.py"
```

---

## 🛠️ Development

### Local Development
```bash
# Start development environment
make dev

# View logs
make logs-dev

# Stop when done
make stop-dev
```

### Features
- **Hot Reload**: Code changes automatically restart bot
- **Source Mounting**: Edit files locally, changes reflect immediately
- **No Health Checks**: Faster restarts during development
- **Separate Network**: Isolated from production

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

### Features
- **Health Checks**: Automatic container health monitoring
- **Auto Restart**: Container restarts on failure
- **Optimized**: Production-ready configuration
- **Security**: No source code mounting

---

## 🌐 Server Deployment

### Manual Deployment
```bash
# SSH to server
ssh user@ip

# Clone repository
git clone https://github.com/kitsuiwebster/cozy-bot.git
cd cozy-bot

# Configure tokens
nano .env.prod  # Add production token
nano .env.dev   # Add development token

# Deploy
make prod
```

### Automatic Deployment (CI/CD)
- **Production**: Push to `main` branch → Auto-deploy to production
- **Development**: Push to `dev` branch → Auto-deploy to development

### Server Commands
```bash
# Check both environments
make status

# Switch environments
make stop-prod && make dev    # Switch to dev
make stop-dev && make prod    # Switch to prod

# View logs
make logs-prod
make logs-dev
```

---

## 🔧 Configuration Details

### Environment Variables Explained
| Variable | Production | Development | Description |
|----------|------------|-------------|-------------|
| `COMPOSE_PROJECT_NAME` | `cozy-prod` | `cozy-dev` | Docker project isolation |
| `DISCORD_BOT_TOKEN` | Prod token | Dev token | Bot authentication |
| `CONTAINER_NAME` | `*-prod` | `*-dev` | Container identification |
| `RESTART_POLICY` | `unless-stopped` | `no` | Auto-restart behavior |
| `HEALTH_CHECK_DISABLE` | `false` | `true` | Health monitoring |
| `DEV_CODE_MOUNT` | `/tmp/empty` | `.` | Source code mounting |

### File Structure
```
cozy-bot/
├── .github/
│   └── workflows/
│       ├── dev-deploy.yml      # Development CI/CD workflow
│       └── prod-deploy.yml     # Production CI/CD workflow
├── assets/                     # Bot assets and media files
├── commands/                   # Discord commands source code
├── docs/
│   ├── article.md             # CozyBot article
│   └── setup.md               # Setup documentation
├── reactions/                 # Message reaction source code
├── sounds/                    # Audio files for bot
├── .dockerignore              # Docker ignore rules
├── .env.dev                   # Development config (secret)
├── .env.prod                  # Production config (secret)
├── .gitignore                 # Git ignore rules
├── CHANGELOG.md               # Project changelog
├── deploy-dev.sh              # Development deployment script
├── deploy-prod.sh             # Production deployment script
├── docker-compose.yml         # Unified Docker configuration
├── Dockerfile                 # Docker image configuration
├── LICENSE                    # Project license
├── main.py                    # Bot source code
├── Makefile                   # Convenience commands
├── README.md                  # Project documentation
├── requirements.txt           # Python dependencies
└── voice_time_data.json       # Bot voice time data storage
```
