#!/bin/bash

# AI Stock Analysis - Startup Script
# Usage: ./start.sh [docker|dev]
#   docker - Run everything via Docker Compose (default)
#   dev    - Run backend/frontend locally for development

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check if .env exists, copy from example if not
setup_env() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log "Created .env from .env.example"
        else
            error ".env.example not found"
        fi
    else
        log ".env already exists"
    fi
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker Desktop."
    fi
    log "Docker is running"
}

# Start with Docker Compose
start_docker() {
    log "Starting all services with Docker Compose..."
    docker-compose up -d

    echo ""
    log "Services started!"
    echo "  - Frontend: http://localhost:5173"
    echo "  - Backend:  http://localhost:8000"
    echo "  - Postgres: localhost:5432"
    echo ""
    log "To view logs: docker-compose logs -f"
    log "To stop: docker-compose down"
}

# Start PostgreSQL only (for dev mode)
start_postgres() {
    if docker ps --format '{{.Names}}' | grep -q "aistock-postgres"; then
        log "PostgreSQL already running"
    else
        log "Starting PostgreSQL..."
        docker-compose up -d postgres
        # Wait for postgres to be ready
        log "Waiting for PostgreSQL to be ready..."
        sleep 3
    fi
}

# Start in development mode (local backend/frontend)
start_dev() {
    log "Starting in development mode..."

    # Start only postgres from docker
    start_postgres

    # Backend setup
    log "Setting up backend..."
    cd "$SCRIPT_DIR/backend"

    if [ ! -d "venv" ]; then
        log "Creating Python virtual environment..."
        python -m venv venv
    fi

    # Activate venv and install deps
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi

    log "Installing backend dependencies..."
    pip install -r requirements.txt -q

    log "Running database migrations..."
    alembic upgrade head

    # Start backend in background
    log "Starting backend server..."
    uvicorn app.main:app --reload &
    BACKEND_PID=$!

    # Frontend setup
    log "Setting up frontend..."
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log "Installing frontend dependencies..."
        npm install
    fi

    # Start frontend
    log "Starting frontend server..."
    npm run dev &
    FRONTEND_PID=$!

    echo ""
    log "Services started!"
    echo "  - Frontend: http://localhost:5173"
    echo "  - Backend:  http://localhost:8000"
    echo ""
    log "Press Ctrl+C to stop all services"

    # Trap to cleanup on exit
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

    # Wait for processes
    wait
}

# Main
main() {
    MODE="${1:-docker}"

    echo "========================================"
    echo "  AI Stock Analysis - Startup Script"
    echo "========================================"
    echo ""

    setup_env
    check_docker

    case "$MODE" in
        docker)
            start_docker
            ;;
        dev)
            start_dev
            ;;
        *)
            echo "Usage: ./start.sh [docker|dev]"
            echo "  docker - Run via Docker Compose (default)"
            echo "  dev    - Run locally for development"
            exit 1
            ;;
    esac
}

main "$@"
