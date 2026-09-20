#!/usr/bin/env bash
# =========================================================
# FindMyBoss — Docker Microservices Management CLI
# Usage: ./run-docker.sh [COMMAND] [OPTIONS]
# =========================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Load environment variables if .env exists
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

SCRAPER_PORT="${SCRAPER_PORT:-8003}"

# Ensure host mount directories exist before Docker creates them as root
mkdir -p "$PROJECT_DIR/data/cvs" "$PROJECT_DIR/logs"

COMMAND="${1:-help}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_banner() {
  echo -e "${CYAN}"
  echo "  ███████╗██╗███╗   ██╗██████╗ ███╗   ███╗██╗   ██╗██████╗  ██████╗ ███████╗███████╗"
  echo "  ██╔════╝██║████╗  ██║██╔══██╗████╗ ████║╚██╗ ██╔╝██╔══██╗██╔═══██╗██╔════╝██╔════╝"
  echo "  █████╗  ██║██╔██╗ ██║██║  ██║██╔████╔██║ ╚████╔╝ ██████╔╝██║   ██║███████╗███████╗"
  echo "  ██╔══╝  ██║██║╚██╗██║██║  ██║██║╚██╔╝██║  ╚██╔╝  ██╔══██╗██║   ██║╚════██║╚════██║"
  echo "  ██║     ██║██║ ╚████║██████╔╝██║ ╚═╝ ██║   ██║   ██████╔╝╚██████╔╝███████║███████║"
  echo "  ╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝   ╚═╝   ╚═════╝  ╚═════╝ ╚══════╝╚══════╝"
  echo -e "${NC}"
  echo -e "  ${YELLOW}Microservices Stack: web (8000) | renderer (8001) | scraper (${SCRAPER_PORT})${NC}"
  echo ""
}

case "$COMMAND" in
  up|start)
    print_banner
    echo -e "${GREEN}🚀 Starting all 3 FindMyBoss Microservices...${NC}"
    docker compose up -d --build
    echo ""
    echo -e "${GREEN}=========================================================="
    echo -e "  ✅ FindMyBoss Microservices System is Running!"
    echo -e ""
    echo -e "  🌐 Web Studio:       http://localhost:8000"
    echo -e "  📄 LaTeX Renderer:   http://localhost:8001/health"
    echo -e "  🕷️  Job Scraper:      http://localhost:${SCRAPER_PORT}/health"
    echo -e "==========================================================${NC}"
    docker compose ps
    ;;

  down|stop)
    echo -e "${YELLOW}🛑 Stopping all FindMyBoss microservices...${NC}"
    docker compose down
    echo -e "${GREEN}✅ All containers stopped. Data persisted in ./data and ./logs${NC}"
    ;;

  build)
    print_banner
    echo -e "${CYAN}🔨 Building all microservice Docker images...${NC}"
    docker compose build --no-cache
    echo -e "${GREEN}✅ Build complete!${NC}"
    docker compose images
    ;;

  restart)
    SERVICE="${2:-}"
    if [ -n "$SERVICE" ]; then
      echo -e "${YELLOW}🔄 Restarting service: ${SERVICE}...${NC}"
      docker compose restart "$SERVICE"
    else
      echo -e "${YELLOW}🔄 Restarting all microservices...${NC}"
      docker compose restart
    fi
    ;;

  status|ps)
    echo -e "${CYAN}📊 FindMyBoss Microservices Status:${NC}"
    docker compose ps
    echo ""
    echo -e "${CYAN}🔍 Health Checks:${NC}"
    for port in 8000 8001 "$SCRAPER_PORT"; do
      svc="web"; [ "$port" -eq 8001 ] && svc="renderer"; [ "$port" -eq "$SCRAPER_PORT" ] && svc="scraper"
      if curl -sf "http://localhost:${port}/health" > /dev/null 2>&1 || \
         curl -sf "http://localhost:${port}/api/stats" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ ${svc} (port ${port}): healthy${NC}"
      else
        echo -e "  ${RED}❌ ${svc} (port ${port}): unreachable${NC}"
      fi
    done
    ;;

  logs)
    SERVICE="${2:-}"
    if [ -n "$SERVICE" ]; then
      echo -e "${CYAN}📋 Logs for service: ${SERVICE}${NC}"
      docker compose logs -f "$SERVICE"
    else
      echo -e "${CYAN}📋 Logs for all services (Ctrl+C to exit):${NC}"
      docker compose logs -f
    fi
    ;;

  scrape)
    echo -e "${CYAN}🕷️  Triggering on-demand job scrape via API...${NC}"
    curl -s -X POST http://localhost:8000/api/scraper/run | python3 -m json.tool || \
    curl -s -X POST "http://localhost:${SCRAPER_PORT}/api/scrape" | python3 -m json.tool
    ;;

  scrape-status)
    echo -e "${CYAN}📊 Scraper Status:${NC}"
    curl -s http://localhost:8000/api/scraper/status | python3 -m json.tool
    ;;

  shell)
    SERVICE="${2:-web}"
    echo -e "${CYAN}🐚 Opening shell in ${SERVICE} container...${NC}"
    docker compose exec "$SERVICE" /bin/bash
    ;;

  prune)
    echo -e "${RED}⚠️  Removing stopped containers and unused images...${NC}"
    docker compose down --rmi local --volumes --remove-orphans
    echo -e "${GREEN}✅ Cleanup complete.${NC}"
    ;;

  help|*)
    print_banner
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  up, start          Build & start all 3 microservices"
    echo "  down, stop         Stop all microservices (data is preserved)"
    echo "  build              Rebuild all Docker images from scratch"
    echo "  restart [service]  Restart all or a specific service (web|renderer|scraper)"
    echo "  status, ps         Show container status + health check summary"
    echo "  logs [service]     Follow logs (all or specific: web|renderer|scraper)"
    echo "  scrape             Trigger on-demand job scraping"
    echo "  scrape-status      Check current scraper status"
    echo "  shell [service]    Open interactive shell in container (default: web)"
    echo "  prune              Remove containers & images (data preserved)"
    echo ""
    echo "Examples:"
    echo "  $0 up                   # Start everything"
    echo "  $0 logs scraper         # Follow scraper logs"
    echo "  $0 restart renderer     # Restart only the renderer"
    echo "  $0 shell web            # Shell into web container"
    ;;
esac
