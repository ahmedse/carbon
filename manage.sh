#!/bin/bash
#
# Carbon Platform Service Manager
# A robust script to manage all Carbon services
#
# Usage: ./manage.sh <command> [options]
#
# Commands:
#   start      - Start all services (kills existing, cleans cache)
#   stop       - Gracefully stop all services
#   restart    - Stop then start all services
#   status     - Show service status
#   logs       - View logs (all|backend|frontend)
#   health     - Run health checks
#   clean      - Deep clean (stop, clear all caches, archive logs)
#   migrate    - Run Django migrations
#   shell      - Open Django shell
#   test       - Run backend tests
#   killall    - Emergency force kill everything
#   help       - Show help
#

# Exit on undefined variables only (not on errors, we handle those)
set -u

# ============================================================================
# CONFIGURATION
# ============================================================================

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# Paths
readonly PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
readonly BACKEND_DIR="$PROJECT_ROOT/backend"
readonly FRONTEND_DIR="$PROJECT_ROOT/carbon-frontend"
readonly LOGS_DIR="$PROJECT_ROOT/logs"
readonly PIDS_DIR="$PROJECT_ROOT/.pids"

# Ports
readonly BACKEND_PORT=8001
readonly FRONTEND_PORT=5173

# Log files
readonly BACKEND_LOG="$LOGS_DIR/backend.log"
readonly FRONTEND_LOG="$LOGS_DIR/frontend.log"

# PID files
readonly BACKEND_PID="$PIDS_DIR/backend.pid"
readonly FRONTEND_PID="$PIDS_DIR/frontend.pid"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

setup_dirs() {
    mkdir -p "$LOGS_DIR" "$PIDS_DIR"
}

print_header() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${GREEN}🌱${NC} ${MAGENTA}Carbon Platform Manager${NC}                       ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

log_error() {
    echo -e "${RED}✗${NC}  $1"
}

log_step() {
    echo -e "${MAGENTA}→${NC}  $1"
}

# Check if a command exists
has_command() {
    command -v "$1" &>/dev/null
}

# Check if a port is in use
port_in_use() {
    local port=$1
    lsof -Pi ":$port" -sTCP:LISTEN -t &>/dev/null
}

# Get PIDs using a port
get_port_pids() {
    local port=$1
    lsof -ti ":$port" 2>/dev/null || echo ""
}

# Kill all processes on a port
kill_port() {
    local port=$1
    local pids
    pids=$(get_port_pids "$port")
    
    if [[ -n "$pids" ]]; then
        log_warn "Port $port occupied - killing processes: $pids"
        echo "$pids" | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Check if PID is running
pid_running() {
    local pid=$1
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# Read PID from file
read_pid() {
    local pid_file=$1
    [[ -f "$pid_file" ]] && cat "$pid_file" 2>/dev/null || echo ""
}

# Get Python executable (uses venv)
get_python() {
    if [[ -f "$BACKEND_DIR/venv/bin/python" ]]; then
        echo "$BACKEND_DIR/venv/bin/python"
    elif [[ -f "$BACKEND_DIR/.venv/bin/python" ]]; then
        echo "$BACKEND_DIR/.venv/bin/python"
    elif [[ -f "$PROJECT_ROOT/venv/bin/python" ]]; then
        echo "$PROJECT_ROOT/venv/bin/python"
    elif [[ -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
        echo "$PROJECT_ROOT/.venv/bin/python"
    else
        echo ""
    fi
}

# Activate venv and return activation command
get_venv_activate() {
    if [[ -f "$BACKEND_DIR/venv/bin/activate" ]]; then
        echo "source $BACKEND_DIR/venv/bin/activate"
    elif [[ -f "$BACKEND_DIR/.venv/bin/activate" ]]; then
        echo "source $BACKEND_DIR/.venv/bin/activate"
    elif [[ -f "$PROJECT_ROOT/venv/bin/activate" ]]; then
        echo "source $PROJECT_ROOT/venv/bin/activate"
    elif [[ -f "$PROJECT_ROOT/.venv/bin/activate" ]]; then
        echo "source $PROJECT_ROOT/.venv/bin/activate"
    else
        echo ""
    fi
}

# Create venv if not exists
ensure_venv() {
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_step "Creating Python virtual environment..."
        cd "$BACKEND_DIR" || return 1
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        log_success "Virtual environment created and dependencies installed"
    fi
}

# Ensure frontend dependencies
ensure_frontend_deps() {
    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        log_step "Installing frontend dependencies..."
        cd "$FRONTEND_DIR" || return 1
        npm install
        log_success "Frontend dependencies installed"
    fi
}

# ============================================================================
# SERVICE CONTROL FUNCTIONS
# ============================================================================

# Kill a service by PID file
kill_service() {
    local name=$1
    local pid_file=$2
    local pid
    pid=$(read_pid "$pid_file")
    
    if pid_running "$pid"; then
        log_step "Stopping $name (PID: $pid)..."
        
        # Try graceful kill first
        kill "$pid" 2>/dev/null || true
        
        # Wait up to 5 seconds
        local count=0
        while pid_running "$pid" && [[ $count -lt 5 ]]; do
            sleep 1
            ((count++))
        done
        
        # Force kill if still running
        if pid_running "$pid"; then
            log_warn "Force killing $name..."
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi
        
        log_success "$name stopped"
    fi
    
    rm -f "$pid_file"
}

# Start backend (Django)
start_backend() {
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_error "Python venv not found! Creating one..."
        ensure_venv
        python=$(get_python)
        if [[ -z "$python" ]]; then
            log_error "Failed to create venv. Run: cd backend && python3 -m venv venv && pip install -r requirements.txt"
            return 1
        fi
    fi
    
    log_step "Starting Django Backend..."
    
    # Kill any existing
    kill_service "Backend" "$BACKEND_PID"
    kill_port "$BACKEND_PORT"
    
    # Clear Python cache
    find "$BACKEND_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    # Start Django runserver
    cd "$BACKEND_DIR" || return 1
    nohup "$python" manage.py runserver 0.0.0.0:$BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    
    # Verify
    sleep 3
    if port_in_use "$BACKEND_PORT"; then
        log_success "Backend started (PID: $(cat "$BACKEND_PID"), Port: $BACKEND_PORT)"
        return 0
    else
        log_error "Backend failed to start"
        echo ""
        echo -e "${YELLOW}Last 20 lines of log:${NC}"
        tail -20 "$BACKEND_LOG" 2>/dev/null || true
        return 1
    fi
}

# Start frontend (Vite)
start_frontend() {
    log_step "Starting Vite Frontend..."
    
    # Kill any existing
    kill_service "Frontend" "$FRONTEND_PID"
    kill_port "$FRONTEND_PORT"
    
    # Ensure dependencies
    ensure_frontend_deps
    
    # Clear Vite cache
    rm -rf "$FRONTEND_DIR/node_modules/.vite" 2>/dev/null || true
    
    # Start
    cd "$FRONTEND_DIR" || return 1
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID"
    
    # Verify (frontend takes longer)
    sleep 5
    if port_in_use "$FRONTEND_PORT"; then
        log_success "Frontend started (PID: $(cat "$FRONTEND_PID"), Port: $FRONTEND_PORT)"
        return 0
    else
        log_error "Frontend failed to start"
        echo ""
        echo -e "${YELLOW}Last 20 lines of log:${NC}"
        tail -20 "$FRONTEND_LOG" 2>/dev/null || true
        return 1
    fi
}

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

cmd_start() {
    print_header
    log_info "Starting Carbon Platform services..."
    echo ""
    
    # Check dependencies
    log_info "Checking dependencies..."
    local deps_ok=true
    
    if has_command python3; then
        log_success "Python3 found: $(python3 --version)"
    else
        log_error "Python3 not found"
        deps_ok=false
    fi
    
    if has_command npm; then
        log_success "npm found: $(npm --version)"
    else
        log_error "npm not found"
        deps_ok=false
    fi
    
    if has_command pg_isready && pg_isready -h localhost -p 5432 &>/dev/null; then
        log_success "PostgreSQL running"
    else
        log_warn "PostgreSQL may not be running - trying to start..."
        sudo systemctl start postgresql 2>/dev/null || log_warn "Could not start PostgreSQL automatically"
    fi
    
    if [[ "$deps_ok" == false ]]; then
        log_error "Missing dependencies. Cannot start."
        return 1
    fi
    
    echo ""
    log_info "Starting services..."
    echo ""
    
    local all_ok=true
    
    start_backend || all_ok=false
    start_frontend || all_ok=false
    
    echo ""
    if [[ "$all_ok" == true ]]; then
        log_success "All services started!"
        echo ""
        echo -e "  ${CYAN}Frontend:${NC}  ${GREEN}http://localhost:$FRONTEND_PORT/carbon/${NC}"
        echo -e "  ${CYAN}Backend:${NC}   ${GREEN}http://localhost:$BACKEND_PORT${NC}"
        echo -e "  ${CYAN}API Docs:${NC}  ${GREEN}http://localhost:$BACKEND_PORT/swagger/${NC}"
        echo -e "  ${CYAN}Admin:${NC}     ${GREEN}http://localhost:$BACKEND_PORT/admin/${NC}"
    else
        log_warn "Some services failed to start. Check logs with: ./manage.sh logs"
    fi
    echo ""
}

cmd_stop() {
    print_header
    log_info "Stopping Carbon Platform services..."
    echo ""
    
    kill_service "Frontend" "$FRONTEND_PID"
    kill_service "Backend" "$BACKEND_PID"
    
    # Clean up any remaining processes
    log_step "Cleaning up remaining processes..."
    pkill -9 -f "manage.py runserver" 2>/dev/null || true
    pkill -9 -f "vite" 2>/dev/null || true
    
    # Free ports
    kill_port "$BACKEND_PORT"
    kill_port "$FRONTEND_PORT"
    
    # Remove PID files
    rm -f "$PIDS_DIR"/*.pid 2>/dev/null || true
    
    echo ""
    log_success "All services stopped"
    echo ""
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    print_header
    log_info "Service Status"
    echo ""
    
    # Backend
    local backend_pid
    backend_pid=$(read_pid "$BACKEND_PID")
    printf "  %-18s" "Backend API:"
    if pid_running "$backend_pid" && port_in_use "$BACKEND_PORT"; then
        echo -e "${GREEN}RUNNING${NC} (PID: $backend_pid, Port: $BACKEND_PORT)"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    # Frontend
    local frontend_pid
    frontend_pid=$(read_pid "$FRONTEND_PID")
    printf "  %-18s" "Frontend:"
    if pid_running "$frontend_pid" && port_in_use "$FRONTEND_PORT"; then
        echo -e "${GREEN}RUNNING${NC} (PID: $frontend_pid, Port: $FRONTEND_PORT)"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo ""
    log_info "Infrastructure"
    echo ""
    
    printf "  %-18s" "PostgreSQL:"
    if pg_isready -h localhost -p 5432 &>/dev/null 2>&1; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    printf "  %-18s" "Python venv:"
    local python
    python=$(get_python)
    if [[ -n "$python" ]]; then
        echo -e "${GREEN}FOUND${NC} ($python)"
    else
        echo -e "${YELLOW}NOT FOUND${NC}"
    fi
    
    printf "  %-18s" "Node modules:"
    if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
        echo -e "${GREEN}INSTALLED${NC}"
    else
        echo -e "${YELLOW}NOT INSTALLED${NC}"
    fi
    
    echo ""
}

cmd_logs() {
    local service="${1:-all}"
    
    case "$service" in
        backend)
            echo -e "${CYAN}==> Backend Logs (Ctrl+C to exit)${NC}"
            tail -f "$BACKEND_LOG"
            ;;
        frontend)
            echo -e "${CYAN}==> Frontend Logs (Ctrl+C to exit)${NC}"
            tail -f "$FRONTEND_LOG"
            ;;
        all|*)
            echo -e "${CYAN}==> All Logs (Ctrl+C to exit)${NC}"
            tail -f "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null
            ;;
    esac
}

cmd_health() {
    print_header
    log_info "Health Checks"
    echo ""
    
    printf "  %-18s" "Backend API:"
    local backend_response
    backend_response=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$BACKEND_PORT/carbon-api/health/" 2>/dev/null || echo "000")
    if [[ "$backend_response" == "200" ]]; then
        echo -e "${GREEN}HEALTHY${NC} (HTTP $backend_response)"
    else
        echo -e "${RED}UNHEALTHY${NC} (HTTP $backend_response)"
    fi
    
    printf "  %-18s" "Frontend:"
    local frontend_response
    frontend_response=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$FRONTEND_PORT/carbon/" 2>/dev/null || echo "000")
    if [[ "$frontend_response" == "200" || "$frontend_response" == "304" ]]; then
        echo -e "${GREEN}HEALTHY${NC} (HTTP $frontend_response)"
    else
        echo -e "${RED}UNHEALTHY${NC} (HTTP $frontend_response)"
    fi
    
    printf "  %-18s" "PostgreSQL:"
    if pg_isready -h localhost -p 5432 &>/dev/null 2>&1; then
        echo -e "${GREEN}HEALTHY${NC}"
    else
        echo -e "${RED}UNHEALTHY${NC}"
    fi
    
    echo ""
}

cmd_migrate() {
    print_header
    log_info "Running Django migrations..."
    echo ""
    
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi
    
    cd "$BACKEND_DIR" || return 1
    "$python" manage.py migrate
    
    echo ""
    log_success "Migrations complete"
    echo ""
}

cmd_shell() {
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi
    
    cd "$BACKEND_DIR" || return 1
    "$python" manage.py shell
}

cmd_test() {
    print_header
    log_info "Running backend tests..."
    echo ""
    
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi
    
    cd "$BACKEND_DIR" || return 1
    "$python" -m pytest "${@:2}"
}

cmd_clean() {
    print_header
    log_info "Deep cleaning Carbon Platform..."
    echo ""
    
    # Stop all services
    log_step "Stopping all services..."
    cmd_stop &>/dev/null
    
    # Clean PID files
    log_step "Removing PID files..."
    rm -f "$PIDS_DIR"/*.pid 2>/dev/null || true
    log_success "PID files removed"
    
    # Clean Python cache
    log_step "Cleaning Python cache..."
    find "$BACKEND_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$BACKEND_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    log_success "Python cache cleared"
    
    # Clean frontend cache
    log_step "Cleaning frontend cache..."
    rm -rf "$FRONTEND_DIR/node_modules/.vite" 2>/dev/null || true
    rm -rf "$FRONTEND_DIR/dist" 2>/dev/null || true
    log_success "Frontend cache cleared"
    
    # Archive logs
    log_step "Archiving logs..."
    if [[ -d "$LOGS_DIR" ]] && ls "$LOGS_DIR"/*.log &>/dev/null 2>&1; then
        mkdir -p "$LOGS_DIR/archive"
        local ts
        ts=$(date +%Y%m%d_%H%M%S)
        tar -czf "$LOGS_DIR/archive/logs_$ts.tar.gz" -C "$LOGS_DIR" *.log 2>/dev/null || true
        : > "$BACKEND_LOG"
        : > "$FRONTEND_LOG"
        log_success "Logs archived to logs/archive/logs_$ts.tar.gz"
    else
        log_info "No logs to archive"
    fi
    
    echo ""
    log_success "Deep clean complete!"
    log_info "Run './manage.sh start' to start fresh"
    echo ""
}

cmd_killall() {
    print_header
    log_warn "EMERGENCY: Force killing all Carbon processes..."
    echo ""
    
    # Kill everything
    log_step "Killing all related processes..."
    pkill -9 -f "manage.py runserver" 2>/dev/null || true
    pkill -9 -f "vite" 2>/dev/null || true
    pkill -9 -f "node.*carbon" 2>/dev/null || true
    
    # Force free ports
    log_step "Freeing ports..."
    kill_port "$BACKEND_PORT"
    kill_port "$FRONTEND_PORT"
    
    # Remove all PID files
    rm -f "$PIDS_DIR"/*.pid 2>/dev/null || true
    
    echo ""
    log_success "All processes killed"
    log_warn "This was a force kill (SIGKILL). Use 'stop' for graceful shutdown."
    echo ""
}

cmd_help() {
    print_header
    echo "Usage: ./manage.sh <command> [options]"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo "  start              Start all services (auto-cleans ports & cache)"
    echo "  stop               Gracefully stop all services"
    echo "  restart            Stop then start all services"
    echo "  status             Show service status"
    echo "  logs [service]     View logs (all|backend|frontend)"
    echo "  health             Run health checks"
    echo "  migrate            Run Django migrations"
    echo "  shell              Open Django shell"
    echo "  test               Run backend tests (pytest)"
    echo "  clean              Deep clean (stop, clear caches, archive logs)"
    echo "  killall            Emergency: force kill everything"
    echo "  help               Show this help"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  ./manage.sh start          # Start everything"
    echo "  ./manage.sh stop           # Stop everything"
    echo "  ./manage.sh status         # Check what's running"
    echo "  ./manage.sh logs backend   # View backend logs"
    echo "  ./manage.sh migrate        # Run DB migrations"
    echo "  ./manage.sh clean          # Full cleanup"
    echo ""
    echo -e "${CYAN}Ports:${NC}"
    echo "  Backend:   http://localhost:$BACKEND_PORT"
    echo "  Frontend:  http://localhost:$FRONTEND_PORT/carbon/"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    setup_dirs
    
    local cmd="${1:-help}"
    
    case "$cmd" in
        start)      cmd_start ;;
        stop)       cmd_stop ;;
        restart)    cmd_restart ;;
        status)     cmd_status ;;
        logs)       cmd_logs "${2:-all}" ;;
        health)     cmd_health ;;
        migrate)    cmd_migrate ;;
        shell)      cmd_shell ;;
        test)       cmd_test "$@" ;;
        clean)      cmd_clean ;;
        killall)    cmd_killall ;;
        help|-h|--help) cmd_help ;;
        *)
            log_error "Unknown command: $cmd"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
