# Make Commands

## Global
- `make start-all` - Start all services.
- `make stop-all` - Stop all services.
- `make rebuild-all` - Rebuild and recreate all services.
- `make logs-all` - Tail logs for all services.
- `make status-all` - Show status for all services.
- `make ui` - Show local UI links.

## Bot (Live API)
- `make start` - Start the live bot container.
- `make stop` - Stop and remove the live bot container.
- `make restart` - Restart the live bot container.
- `make rebuild` - Rebuild and recreate the live bot container.
- `make logs` - Tail live bot logs.

## Public API
- `make start-api` - Start the public API container.
- `make stop-api` - Stop and remove the public API container.
- `make restart-api` - Restart the public API container.
- `make rebuild-api` - Rebuild and recreate the public API container.
- `make logs-api` - Tail public API logs.

## Status API
- `make start-status-api` - Start the status API container.
- `make stop-status-api` - Stop and remove the status API container.
- `make restart-status-api` - Restart the status API container.
- `make rebuild-status-api` - Rebuild and recreate the status API container.
- `make logs-status-api` - Tail status API logs.
- `make status-api-db` - Open the status API SQLite DB.

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
- `make seed-db` - Seed CouchDB design views.

## Combined Logs
- `make logs-core` - Tail combined bot + public API logs.

## Maintenance
- `make clean` - Remove Docker resources created by the project.
