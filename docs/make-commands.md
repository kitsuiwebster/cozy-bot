# Make Commands

## Global
- `make start-all` - Start all services.
- `make stop-all` - Stop all services.
- `make rebuild-all` - Rebuild and recreate all services.
- `make logs-all` - Tail logs for all services.
- `make status-all` - Show status for all services.

## Bot (Live API)
- `make start-bot` - Start the live bot container.
- `make stop-bot` - Stop and remove the live bot container.
- `make restart-bot` - Restart the live bot container.
- `make rebuild-bot` - Rebuild and recreate the live bot container.
- `make logs-bot` - Tail live bot logs.
- `make status` - Show live bot status.

## Public API
- `make start-api` - Start the public API container.
- `make stop-api` - Stop and remove the public API container.
- `make restart-api` - Restart the public API container.
- `make rebuild-api` - Rebuild and recreate the public API container.
- `make logs-api` - Tail public API logs.

## Status Page
- `make start-status` - Start the status page container.
- `make stop-status` - Stop and remove the status page container.
- `make restart-status` - Restart the status page container.
- `make rebuild-status` - Recreate the status page container.
- `make logs-status` - Tail status page logs.

## Uptime Kuma
- `make start-kuma` - Start the Uptime Kuma container.
- `make stop-kuma` - Stop and remove the Uptime Kuma container.
- `make restart-kuma` - Restart the Uptime Kuma container.
- `make rebuild-kuma` - Recreate the Uptime Kuma container.
- `make logs-kuma` - Tail Uptime Kuma logs.

## CouchDB
- `make start-db` - Start the CouchDB container.
- `make stop-db` - Stop and remove the CouchDB container.
- `make restart-db` - Restart the CouchDB container.
- `make rebuild-db` - Recreate the CouchDB container.
- `make logs-db` - Tail CouchDB logs.

## Combined Logs
- `make logs-core` - Tail combined bot + public API logs.

## Maintenance
- `make clean` - Remove Docker resources created by the project.
