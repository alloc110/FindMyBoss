.PHONY: help up down build restart status logs scrape web test clean

SCRIPTS_DIR := scripts

# Default target: display help
help:
	@echo "======================================================================"
	@echo "🎯 FindMyBoss Management CLI"
	@echo "======================================================================"
	@echo "Docker Microservices Commands:"
	@echo "  make up              Build & start all 3 microservices (Web, Renderer, Scraper)"
	@echo "  make down            Stop all containers (data is preserved)"
	@echo "  make build           Rebuild all Docker images from scratch"
	@echo "  make restart [s=..]  Restart services (e.g. make restart s=web)"
	@echo "  make status          Show container status + health check summary"
	@echo "  make logs [s=..]     Follow logs (e.g. make logs s=scraper)"
	@echo "  make scrape-docker   Trigger on-demand scraping inside Docker"
	@echo ""
	@echo "Local Development Commands:"
	@echo "  make web             Run FastAPI Web Studio locally"
	@echo "  make scrape          Run Scraper locally via main.py"
	@echo "  make test            Run test suite with pytest"
	@echo "  make clean           Remove temporary cache and build files"
	@echo "======================================================================"

up:
	@bash $(SCRIPTS_DIR)/run-docker.sh up

down:
	@bash $(SCRIPTS_DIR)/run-docker.sh down

build:
	@bash $(SCRIPTS_DIR)/run-docker.sh build

restart:
	@bash $(SCRIPTS_DIR)/run-docker.sh restart $(s)

status:
	@bash $(SCRIPTS_DIR)/run-docker.sh status

logs:
	@bash $(SCRIPTS_DIR)/run-docker.sh logs $(s)

scrape-docker:
	@bash $(SCRIPTS_DIR)/run-docker.sh scrape

web:
	@bash $(SCRIPTS_DIR)/run-web.sh

scrape:
	@bash $(SCRIPTS_DIR)/run-scraper.sh

test:
	@pytest tests/ -v

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
