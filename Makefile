.PHONY: help start-all stop-all \
        start stop restart rebuild-bot logs-bot \
        start-api stop-api restart-api rebuild-api logs-api \
        start-status stop-status restart-status rebuild-status logs-status \
        start-kuma stop-kuma restart-kuma rebuild-kuma logs-kuma \
        start-db stop-db restart-db rebuild-db logs-db \
        start-couchdb stop-couchdb restart-couchdb rebuild-couchdb logs-couchdb \
        rebuild rebuild-all logs logs-all logs-core status status-all clean

ENV_DIR ?= dev
COMPOSE := docker compose -f $(ENV_DIR)/docker-compose.yml

# Default target - show help
help:
	@echo "📚 Available Commands:"
	@echo ""
	@echo "ℹ️  Environment directory: $(ENV_DIR)"
	@echo ""
	@echo "🚀 Global:"
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
	@echo "  make status            - Show bot status"
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
	@echo ""
	@echo "🧩 Mixed:"
	@echo "  make logs-core        - Bot + Public API logs"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean            - Clean up Docker resources"

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

stop-status:
	@echo "🛑 Stopping Status Page only..."
	@$(COMPOSE) stop status-page && $(COMPOSE) rm -f status-page

# ============================================
# STATUS & MAINTENANCE
# ============================================

status:
	@echo "📊 Bot Status:"
	@docker ps --filter name=cozy-live-bot --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

status-all:
	@echo "📊 All Services Status:"
	@docker ps --filter name=cozy --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "🧹 Cleaning up..."
	@docker system prune -a -f
	@docker volume prune -f
