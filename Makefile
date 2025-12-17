.PHONY: help build up down logs logs-cron test-build clean

help:
	@echo "SchoolCafe Menu Sync - Docker Commands"
	@echo ""
	@echo "  make build       - Build the Docker image"
	@echo "  make up          - Start the container in background"
	@echo "  make down        - Stop and remove the container"
	@echo "  make logs        - View container logs"
	@echo "  make logs-cron   - View cron logs"
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

logs:
	docker-compose logs -f

logs-cron:
	docker-compose exec schoolcafe tail -f /var/log/cron.log

test-build:
	docker-compose build --no-cache
	@echo "Build successful!"

clean:
	docker-compose down --rmi all -v
	@echo "Cleaned up containers, images, and volumes"
