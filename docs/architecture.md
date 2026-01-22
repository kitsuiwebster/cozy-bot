# 🏗️ Project Architecture

This repository uses a clean, modular architecture with separate development and production environments.

## 📁 Directory Structure

```
/workspace/
├── dev/                        # 🔧 Development Environment (Independent)
│   ├── .env                   # Dev configuration
│   ├── main.py                # Bot main entry point
│   ├── server.py              # API server
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Docker build config
│   ├── docker-compose.yml     # Docker compose config
│   ├── cogs/                  # Bot command modules
│   ├── api/                   # REST API routes
│   ├── utils/                 # Utility functions
│   ├── data/                  # Dev data (gitignored)
│   └── logs/                  # Dev logs (gitignored)
│
├── prod/                       # 🚀 Production Environment (Independent)
│   ├── .env                   # Prod configuration
│   ├── main.py                # Bot main entry point
│   ├── server.py              # API server
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Docker build config
│   ├── docker-compose.yml     # Docker compose config
│   ├── cogs/                  # Bot command modules
│   ├── api/                   # REST API routes
│   ├── utils/                 # Utility functions
│   ├── data/                  # Prod data (gitignored)
│   └── logs/                  # Prod logs (gitignored)
│
├── scripts/                    # 📜 Deployment & Maintenance Scripts
│   ├── deploy-dev.sh          # Deploy development environment
│   ├── deploy-prod.sh         # Deploy production environment
│   └── backup.sh              # Backup script
│
├── docs/                       # 📚 Shared Documentation
├── assets/                     # 🎨 Shared Assets (images, etc.)
├── .github/                    # 🤖 GitHub Actions & Workflows
│
└── Root Configuration Files
    ├── README.md              # Main project documentation
    ├── CHANGELOG.md           # Version history
    ├── LICENSE                # Project license
    ├── Makefile               # Build commands
    └── .gitignore             # Git ignore rules
```

## 🎯 Design Goals

### 1. **Complete Independence**
Each environment (`dev/` and `prod/`) is completely self-contained:
- Own `.env` configuration
- Own data and logs directories
- Own Docker configuration
- Own bot code (synced from git branches)

### 2. **Clean Architecture**
- Bot-specific code in `dev/` and `prod/`
- Shared documentation and assets at root
- Scripts separated in dedicated directory
- No environment mixing or conflicts

### 3. **Parallel Execution**
Both environments can run simultaneously on the same VPS without conflicts:
- Different container names
- Different network names
- Different data directories
- Different ports

## 📦 Usage

### Development
```bash
make dev        # Deploy dev environment
make logs-dev   # View dev logs
make stop-dev   # Stop dev environment
```

### Production
```bash
make prod       # Deploy prod environment
make logs-prod  # View prod logs
make stop-prod  # Stop prod environment
```

### Utility
```bash
make status     # View all containers
make clean      # Clean Docker resources
```

## 🔄 Deployment Flow

### Development (`make dev`)
1. Script runs from root: `./scripts/deploy-dev.sh`
2. Script changes to `dev/` directory
3. Reads `dev/.env` configuration
4. Builds and deploys using `dev/docker-compose.yml`
5. Container runs with dev-specific settings

### Production (`make prod`)
1. Script runs from root: `./scripts/deploy-prod.sh`
2. Script changes to `prod/` directory
3. Reads `prod/.env` configuration
4. Builds and deploys using `prod/docker-compose.yml`
5. Container runs with prod-specific settings

## 🔐 Security

- `.env` files are gitignored (never committed)
- Data and logs directories are gitignored
- Each environment has isolated data
- Production secrets never leak to dev

## 🛠️ Maintenance

### Updating Dev
1. Make changes on `dev` branch
2. Commit and push
3. Run `make dev` to deploy

### Updating Prod
1. Merge changes to `main` branch
2. Pull on VPS
3. Run `make prod` to deploy

### Backup
```bash
./scripts/backup.sh
```

## 📝 Notes

- Dev environment tracks `dev` git branch
- Prod environment tracks `main` git branch
- Both can coexist without conflicts
- Makefile provides simple interface for all operations
