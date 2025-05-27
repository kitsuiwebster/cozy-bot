# File Structure
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