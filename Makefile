.PHONY: prod dev logs-prod logs-dev stop-prod stop-dev status clean

prod:
	@echo "🚀 Deploying to production..."
	@chmod +x deploy-prod.sh && ./deploy-prod.sh

dev:
	@echo "🚀 Deploying to development..."
	@chmod +x deploy-dev.sh && ./deploy-dev.sh

logs-prod:
	@docker compose --env-file .env.prod logs -f discord-bot

logs-dev:
	@docker compose --env-file .env.dev logs -f discord-bot

stop-prod:
	@echo "🛑 Stopping production..."
	@docker compose --env-file .env.prod down

stop-dev:
	@echo "🛑 Stopping development..."
	@docker compose --env-file .env.dev down

status:
	@echo "📊 Container Status:"
	@docker ps --filter name=cozy-discord-bot --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "🧹 Cleaning up..."
	@docker system prune -a -f
	@docker volume prune -f