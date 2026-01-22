.PHONY: prod dev logs-prod logs-dev stop-prod stop-dev status clean

prod:
	@echo "🚀 Deploying to production..."
	@chmod +x scripts/deploy-prod.sh && ./scripts/deploy-prod.sh

dev:
	@echo "🚀 Deploying to development..."
	@chmod +x scripts/deploy-dev.sh && ./scripts/deploy-dev.sh

logs-prod:
	@docker logs -f cozy-discord-bot-prod

logs-dev:
	@docker logs -f cozy-discord-bot-dev

stop-prod:
	@echo "🛑 Stopping production..."
	@cd prod && docker compose down

stop-dev:
	@echo "🛑 Stopping development..."
	@cd dev && docker compose down

status:
	@echo "📊 Container Status:"
	@docker ps --filter name=cozy-discord-bot --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "🧹 Cleaning up..."
	@docker system prune -a -f
	@docker volume prune -f
