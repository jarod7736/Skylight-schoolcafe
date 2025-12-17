.PHONY: help build up down logs logs-cron test-build clean dev-up dev-restart

help:
	@echo "SchoolCafe Menu Sync - Docker Commands"
	@echo ""
	@echo "Production (code baked into image):"
	@echo "  make build       - Build the Docker image"
	@echo "  make up          - Start the container in background"
	@echo "  make down        - Stop and remove the container"
	@echo ""
	@echo "Development (live code updates):"
	@echo "  make dev-up      - Start in dev mode (code mounted as volume)"
	@echo "  make dev-restart - Restart dev container (picks up code changes)"
	@echo ""
	@echo "Monitoring:"
	@echo "  make logs        - View container logs"
	@echo "  make logs-cron   - View cron logs"
	@echo ""
	@echo "Maintenance:"
	@echo "  make test-build  - Build and test without starting"
	@echo "  make clean       - Stop container and remove images"
	@echo ""

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Container started. View logs with: make logs"

down:
	docker-compose down

dev-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Dev container started. Code changes apply without rebuild."
	@echo "After editing code, run: make dev-restart"

dev-restart:
	docker-compose -f docker-compose.dev.yml restart
	@echo "Dev container restarted with latest code changes"

logs:
	docker-compose logs -f

logs-cron:
	docker-compose exec schoolcafe tail -f /var/log/cron.log

test-build:
	docker-compose build --no-cache
	@echo "Build successful!"

clean:
	docker-compose down --rmi all -v
	docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
	@echo "Cleaned up containers, images, and volumes"
