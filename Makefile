.PHONY: help doctor install start-all stop-all ui \
        start stop restart rebuild-bot logs-bot \
        start-api stop-api restart-api rebuild-api logs-api \
        start-status stop-status restart-status rebuild-status logs-status \
        start-status-api stop-status-api restart-status-api rebuild-status-api logs-status-api status-api-db \
        start-kuma stop-kuma restart-kuma rebuild-kuma logs-kuma \
        start-db stop-db restart-db rebuild-db logs-db seed-db \
        start-couchdb stop-couchdb restart-couchdb rebuild-couchdb logs-couchdb \
        backup-db-offsite list-db-backups \
        rebuild rebuild-all logs logs-all logs-core status-all clean

ENV_DIR ?= stack
COMPOSE := docker compose -f $(ENV_DIR)/infra/docker-compose.yml

# Default target - show help
help:
	@echo "📚 Available Commands:"
	@echo ""
	@echo "ℹ️  Environment directory: $(ENV_DIR)"
	@echo ""
	@echo "🚀 Global:"
	@echo "  make doctor           - Check required local tools for this repo"
	@echo "  make install          - Install Linux CLI tools + web dependencies"
	@echo "  make start-all        - Start ALL services"
	@echo "  make stop-all         - Stop ALL services"
	@echo "  make rebuild-all      - Rebuild ALL services"
	@echo "  make logs-all         - All logs"
	@echo "  make status-all       - Show all services status"
	@echo ""
	@echo "🤖 Bot (Live API):"
	@echo "  make start             - Start bot"
	@echo "  make stop              - Stop bot"
	@echo "  make restart           - Restart bot"
	@echo "  make rebuild           - Rebuild bot"
	@echo "  make logs              - Bot logs"
	@echo ""
	@echo "🌐 Public API:"
	@echo "  make start-api         - Start Public API"
	@echo "  make stop-api          - Stop Public API"
	@echo "  make restart-api       - Restart Public API"
	@echo "  make rebuild-api       - Rebuild Public API"
	@echo "  make logs-api          - Public API logs"
	@echo ""
	@echo "🧭 Status Page (Nginx):"
	@echo "  make start-status      - Start Status Page"
	@echo "  make stop-status       - Stop Status Page"
	@echo "  make restart-status    - Restart Status Page"
	@echo "  make rebuild-status    - Recreate Status Page"
	@echo "  make logs-status       - Status page logs"
	@echo ""
	@echo "🛰️  Status API:"
	@echo "  make start-status-api  - Start Status API"
	@echo "  make stop-status-api   - Stop Status API"
	@echo "  make restart-status-api- Restart Status API"
	@echo "  make rebuild-status-api- Rebuild Status API"
	@echo "  make logs-status-api   - Status API logs"
	@echo "  make status-api-db     - Open Status API SQLite"
	@echo ""
	@echo "📈 Uptime Kuma:"
	@echo "  make start-kuma        - Start Uptime Kuma"
	@echo "  make stop-kuma         - Stop Kuma"
	@echo "  make restart-kuma      - Restart Kuma"
	@echo "  make rebuild-kuma      - Recreate Kuma"
	@echo "  make logs-kuma         - Kuma logs"
	@echo ""
	@echo "🗄️  CouchDB:"
	@echo "  make start-db          - Start CouchDB"
	@echo "  make stop-db           - Stop CouchDB"
	@echo "  make restart-db        - Restart CouchDB"
	@echo "  make rebuild-db        - Recreate CouchDB"
	@echo "  make logs-db           - CouchDB logs"
	@echo "  make seed-db           - Seed CouchDB views"
	@echo ""
	@echo "🧩 Mixed:"
	@echo "  make logs-core        - Bot + Public API logs"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean            - Clean up Docker resources"
	@echo "  make backup-db-offsite - Run offsite CouchDB backup (restic)"
	@echo "  make list-db-backups   - List offsite restic snapshots"
	@echo ""
	@echo "🔗 UI Links:"
	@echo "  make ui               - Show UI links"

# ============================================
# LOCAL SETUP
# ============================================

doctor:
	@echo "🩺 Checking local environment for CozyBot..."
	@echo ""
	@missing=0; \
	check_cmd() { \
		if command -v "$$1" >/dev/null 2>&1; then \
			printf "✅ %-18s %s\n" "$$1" "$$($$2 2>/dev/null | head -n 1)"; \
		else \
			printf "❌ %-18s missing\n" "$$1"; \
			missing=1; \
		fi; \
	}; \
	check_cmd git "git --version"; \
	check_cmd make "make --version"; \
	check_cmd curl "curl --version"; \
	check_cmd jq "jq --version"; \
	check_cmd python3 "python3 --version"; \
	check_cmd pip3 "pip3 --version"; \
	check_cmd node "node --version"; \
	check_cmd npm "npm --version"; \
	check_cmd yarn "yarn --version"; \
	check_cmd ffmpeg "ffmpeg -version"; \
	check_cmd docker "docker --version"; \
	if command -v docker >/dev/null 2>&1; then \
		if docker compose version >/dev/null 2>&1; then \
			printf "✅ %-18s %s\n" "docker compose" "$$(docker compose version | head -n 1)"; \
		else \
			printf "❌ %-18s missing\n" "docker compose"; \
			missing=1; \
		fi; \
	fi; \
	echo ""; \
	if [ "$$missing" -eq 0 ]; then \
		echo "✅ Doctor check passed"; \
	else \
		echo "⚠️ Doctor check found missing tools"; \
		echo "👉 Run: make install"; \
		exit 1; \
	fi

install:
	@echo "📦 Installing Linux CLI tools..."
	@if [ "$$(uname -s)" != "Linux" ]; then echo "❌ make install supports Linux only"; exit 1; fi
	@set -e; \
	if [ "$$(id -u)" -eq 0 ]; then AS_ROOT=""; \
	elif command -v sudo >/dev/null 2>&1; then AS_ROOT="sudo"; \
	else echo "❌ sudo is required (or run as root)"; exit 1; fi; \
	if command -v apt-get >/dev/null 2>&1; then \
		echo "🔧 Package manager: apt-get"; \
		$$AS_ROOT apt-get update; \
		PKGS="ca-certificates"; \
		command -v git >/dev/null 2>&1 || PKGS="$$PKGS git"; \
		command -v make >/dev/null 2>&1 || PKGS="$$PKGS make"; \
		command -v curl >/dev/null 2>&1 || PKGS="$$PKGS curl"; \
		command -v jq >/dev/null 2>&1 || PKGS="$$PKGS jq"; \
		command -v python3 >/dev/null 2>&1 || PKGS="$$PKGS python3"; \
		command -v pip3 >/dev/null 2>&1 || PKGS="$$PKGS python3-pip"; \
		python3 -m venv --help >/dev/null 2>&1 || PKGS="$$PKGS python3-venv"; \
		command -v ffmpeg >/dev/null 2>&1 || PKGS="$$PKGS ffmpeg"; \
		command -v node >/dev/null 2>&1 || PKGS="$$PKGS nodejs"; \
		command -v npm >/dev/null 2>&1 || PKGS="$$PKGS npm"; \
		command -v docker >/dev/null 2>&1 || PKGS="$$PKGS docker.io"; \
		if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then PKGS="$$PKGS docker-compose-plugin"; fi; \
		echo "📦 apt packages to install:$$PKGS"; \
		$$AS_ROOT apt-get install -y $$PKGS; \
	elif command -v dnf >/dev/null 2>&1; then \
		echo "🔧 Package manager: dnf"; \
		PKGS="ca-certificates"; \
		command -v git >/dev/null 2>&1 || PKGS="$$PKGS git"; \
		command -v make >/dev/null 2>&1 || PKGS="$$PKGS make"; \
		command -v curl >/dev/null 2>&1 || PKGS="$$PKGS curl"; \
		command -v jq >/dev/null 2>&1 || PKGS="$$PKGS jq"; \
		command -v python3 >/dev/null 2>&1 || PKGS="$$PKGS python3"; \
		command -v pip3 >/dev/null 2>&1 || PKGS="$$PKGS python3-pip"; \
		command -v ffmpeg >/dev/null 2>&1 || PKGS="$$PKGS ffmpeg"; \
		command -v node >/dev/null 2>&1 || PKGS="$$PKGS nodejs"; \
		command -v npm >/dev/null 2>&1 || PKGS="$$PKGS npm"; \
		command -v docker >/dev/null 2>&1 || PKGS="$$PKGS docker"; \
		echo "📦 dnf packages to install:$$PKGS"; \
		$$AS_ROOT dnf install -y $$PKGS; \
		if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then \
			$$AS_ROOT dnf install -y docker-compose-plugin || true; \
		fi; \
	elif command -v pacman >/dev/null 2>&1; then \
		echo "🔧 Package manager: pacman"; \
		PKGS="ca-certificates"; \
		command -v git >/dev/null 2>&1 || PKGS="$$PKGS git"; \
		command -v make >/dev/null 2>&1 || PKGS="$$PKGS make"; \
		command -v curl >/dev/null 2>&1 || PKGS="$$PKGS curl"; \
		command -v jq >/dev/null 2>&1 || PKGS="$$PKGS jq"; \
		command -v python3 >/dev/null 2>&1 || PKGS="$$PKGS python"; \
		command -v pip3 >/dev/null 2>&1 || PKGS="$$PKGS python-pip"; \
		command -v ffmpeg >/dev/null 2>&1 || PKGS="$$PKGS ffmpeg"; \
		command -v node >/dev/null 2>&1 || PKGS="$$PKGS nodejs"; \
		command -v npm >/dev/null 2>&1 || PKGS="$$PKGS npm"; \
		command -v docker >/dev/null 2>&1 || PKGS="$$PKGS docker"; \
		if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then PKGS="$$PKGS docker-compose"; fi; \
		echo "📦 pacman packages to install:$$PKGS"; \
		$$AS_ROOT pacman -Sy --noconfirm $$PKGS; \
	elif command -v zypper >/dev/null 2>&1; then \
		echo "🔧 Package manager: zypper"; \
		PKGS="ca-certificates"; \
		command -v git >/dev/null 2>&1 || PKGS="$$PKGS git"; \
		command -v make >/dev/null 2>&1 || PKGS="$$PKGS make"; \
		command -v curl >/dev/null 2>&1 || PKGS="$$PKGS curl"; \
		command -v jq >/dev/null 2>&1 || PKGS="$$PKGS jq"; \
		command -v python3 >/dev/null 2>&1 || PKGS="$$PKGS python3"; \
		command -v pip3 >/dev/null 2>&1 || PKGS="$$PKGS python3-pip"; \
		command -v ffmpeg >/dev/null 2>&1 || PKGS="$$PKGS ffmpeg"; \
		command -v node >/dev/null 2>&1 || PKGS="$$PKGS nodejs"; \
		command -v npm >/dev/null 2>&1 || PKGS="$$PKGS npm"; \
		command -v docker >/dev/null 2>&1 || PKGS="$$PKGS docker"; \
		if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then PKGS="$$PKGS docker-compose"; fi; \
		echo "📦 zypper packages to install:$$PKGS"; \
		$$AS_ROOT zypper --non-interactive install $$PKGS; \
	else \
		echo "❌ Unsupported Linux package manager"; \
		exit 1; \
	fi; \
	if ! command -v yarn >/dev/null 2>&1; then \
		if command -v corepack >/dev/null 2>&1; then \
			echo "📦 Enabling yarn via corepack..."; \
			$$AS_ROOT corepack enable; \
			$$AS_ROOT corepack prepare yarn@stable --activate; \
		else \
			echo "📦 Installing yarn via npm..."; \
			$$AS_ROOT npm install -g yarn; \
		fi; \
	fi
	@echo "🌐 Installing web deps (yarn)..."
	@cd web && yarn install --no-lockfile
	@echo ""
	@$(MAKE) doctor
	@echo "✅ Install complete"

# ============================================
# START / STOP
# ============================================

start-all:
	@echo "🚀 Starting all services..."
	@$(COMPOSE) up -d

stop-all:
	@echo "🛑 Stopping ALL services..."
	@$(COMPOSE) down

start:
	@echo "🤖 Starting bot..."
	@$(COMPOSE) up -d discord-bot

stop:
	@echo "🛑 Stopping bot..."
	@$(COMPOSE) stop discord-bot && $(COMPOSE) rm -f discord-bot

restart:
	@echo "🔄 Restarting bot..."
	@$(COMPOSE) restart discord-bot

start-kuma:
	@echo "🏗️  Starting Uptime Kuma..."
	@$(COMPOSE) up -d uptime-kuma

start-couchdb:
	@echo "🏗️  Starting CouchDB..."
	@$(COMPOSE) up -d couchdb

start-db: start-couchdb

start-status:
	@echo "🏗️  Starting Status Page..."
	@$(COMPOSE) up -d status-page

start-status-api:
	@echo "🏗️  Starting Status API..."
	@$(COMPOSE) up -d status-api

# ============================================
# STATUS API DB
# ============================================

status-api-db:
	@docker run --rm -it --user 0 -v cozy-status-api-data:/data keinos/sqlite3 sqlite3 /data/status.db

start-api:
	@echo "🌐 Starting Public API..."
	@$(COMPOSE) up -d api

# ============================================
# RESTART
# ============================================

restart-kuma:
	@echo "🔄 Restarting Uptime Kuma..."
	@$(COMPOSE) restart uptime-kuma

restart-couchdb:
	@echo "🔄 Restarting CouchDB..."
	@$(COMPOSE) restart couchdb

restart-db: restart-couchdb

restart-api:
	@echo "🔄 Restarting Public API..."
	@$(COMPOSE) restart api

restart-status:
	@echo "🔄 Restarting Status Page..."
	@$(COMPOSE) restart status-page

restart-status-api:
	@echo "🔄 Restarting Status API..."
	@$(COMPOSE) restart status-api

# ============================================
# REBUILD
# ============================================

rebuild:
	@echo "🔨 Rebuilding bot with fresh dependencies..."
	@$(COMPOSE) stop discord-bot
	@$(COMPOSE) rm -f discord-bot
	@$(COMPOSE) build --no-cache discord-bot
	@$(COMPOSE) up -d discord-bot
	@echo "✅ Bot rebuilt and restarted!"

rebuild-api:
	@echo "🔨 Rebuilding Public API with fresh dependencies..."
	@$(COMPOSE) stop api
	@$(COMPOSE) rm -f api
	@$(COMPOSE) build --no-cache api
	@$(COMPOSE) up -d api
	@echo "✅ Public API rebuilt and restarted!"

rebuild-status:
	@echo "🔨 Recreating Status Page..."
	@$(COMPOSE) stop status-page
	@$(COMPOSE) rm -f status-page
	@$(COMPOSE) up -d status-page
	@echo "✅ Status Page recreated!"

rebuild-status-api:
	@echo "🔨 Rebuilding Status API..."
	@$(COMPOSE) stop status-api
	@$(COMPOSE) rm -f status-api
	@$(COMPOSE) build --no-cache status-api
	@$(COMPOSE) up -d status-api
	@echo "✅ Status API rebuilt and restarted!"

rebuild-kuma:
	@echo "🔨 Recreating Uptime Kuma..."
	@$(COMPOSE) stop uptime-kuma
	@$(COMPOSE) rm -f uptime-kuma
	@$(COMPOSE) up -d uptime-kuma
	@echo "✅ Kuma recreated!"

rebuild-couchdb:
	@echo "🔨 Recreating CouchDB..."
	@$(COMPOSE) stop couchdb
	@$(COMPOSE) rm -f couchdb
	@$(COMPOSE) up -d couchdb
	@echo "✅ CouchDB recreated!"

rebuild-db: rebuild-couchdb

rebuild-all:
	@echo "🔨 Full rebuild of ALL services..."
	@$(COMPOSE) down
	@$(COMPOSE) build --no-cache
	@$(COMPOSE) up -d
	@echo "✅ All services rebuilt and restarted!"

# ============================================
# LOGS
# ============================================

logs:
	@docker logs -f cozy-live-bot

logs-api:
	@docker logs -f cozy-public-api

logs-kuma:
	@$(COMPOSE) logs -f uptime-kuma

logs-status:
	@$(COMPOSE) logs -f status-page

logs-status-api:
	@$(COMPOSE) logs -f status-api

logs-couchdb:
	@$(COMPOSE) logs -f couchdb

logs-db: logs-couchdb

logs-all:
	@$(COMPOSE) logs -f

logs-core:
	@$(COMPOSE) logs -f discord-bot api

# ============================================
# STOP SINGLE SERVICE
# ============================================

# keep aliases for compatibility
rebuild-bot: rebuild
logs-bot: logs

stop-api:
	@echo "🛑 Stopping Public API only..."
	@$(COMPOSE) stop api && $(COMPOSE) rm -f api

stop-kuma:
	@echo "🛑 Stopping Kuma only..."
	@$(COMPOSE) stop uptime-kuma && $(COMPOSE) rm -f uptime-kuma

stop-couchdb:
	@echo "🛑 Stopping CouchDB only..."
	@$(COMPOSE) stop couchdb && $(COMPOSE) rm -f couchdb

stop-db: stop-couchdb

seed-db:
	@echo "🌱 Seeding CouchDB views and docs..."
	@./stack/infra/couchdb-seed/seed-db.sh

stop-status:
	@echo "🛑 Stopping Status Page only..."
	@$(COMPOSE) stop status-page && $(COMPOSE) rm -f status-page

stop-status-api:
	@echo "🛑 Stopping Status API only..."
	@$(COMPOSE) stop status-api && $(COMPOSE) rm -f status-api

status-all:
	@echo "📊 All Services Status:"
	@docker ps --filter name=cozy --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "🧹 Cleaning up..."
	@docker system prune -a -f
	@docker volume prune -f

backup-db-offsite:
	@./scripts/backup_couchdb_offsite.sh

list-db-backups:
	@set -a; . /root/.restic-couchdb.env; set +a; restic snapshots

# ============================================
# UI LINKS
# ============================================

ui:
	@echo "🔗 UI Links:"
	@. ./stack/infra/.env && \
	STATUS_PORT=$${STATUS_PAGE_PORT:-8080} && \
	KUMA_PORT=$${UPTIME_KUMA_PORT:-3001} && \
	API_PORT=$${API_PORT:-8001} && \
	DB_PORT=$${COUCHDB_PORT:-5985} && \
	echo "  Status Page:   http://localhost:$${STATUS_PORT}" && \
	echo "  Uptime Kuma:   http://localhost:$${KUMA_PORT}" && \
	echo "  Public API:    http://localhost:$${API_PORT}/docs" && \
	echo "  CouchDB:       http://localhost:$${DB_PORT}/_utils"
