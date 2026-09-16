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
#   clean-ports - Force-free backend/frontend ports (+ stray Vite ports)
#   migrate    - Run Django migrations
#   shell      - Open Django shell
#   test       - Run backend tests
#   killall    - Emergency force kill everything
#   help       - Show help
#
# Ports (fixed; Vite uses strictPort — never silently moves to 5180+)
#   Backend:  8009
#   Frontend: 5179
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

# Ports (must stay fixed — Vite strictPort:true; spillover 5180+ = orphan, kill it)
readonly BACKEND_PORT=8009
readonly FRONTEND_PORT=5179
# Extra frontend ports Vite may have taken before strictPort / from orphan processes
readonly FRONTEND_SPILL_PORTS=(5180 5181 5182 5183 5184 5185)

# Load API prefix from backend .env (default to /carbon-api/ if not set)
DJANGO_API_PREFIX=$(grep -E '^DJANGO_API_PREFIX=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d'=' -f2 || true)
DJANGO_API_PREFIX=${DJANGO_API_PREFIX:-/carbon-api/}

# Frontend public URL from VITE_BASE (all brand presets use "/" — not /carbon/).
# Trailing slash always present so status/health/help stay consistent.
frontend_public_url() {
    local base
    base=$(grep -E '^VITE_BASE=' "$FRONTEND_DIR/.env" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '[:space:]"' || true)
    base=${base:-/}
    if [[ "$base" != /* ]]; then
        base="/$base"
    fi
    if [[ "$base" != */ ]]; then
        base="${base}/"
    fi
    echo "http://localhost:${FRONTEND_PORT}${base}"
}

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

# Check if a port is in use (lsof + ss — WSL-safe)
port_in_use() {
    local port=$1
    if has_command lsof && lsof -Pi ":$port" -sTCP:LISTEN -t &>/dev/null; then
        return 0
    fi
    if has_command ss && ss -tln "( sport = :$port )" 2>/dev/null | grep -q ":$port"; then
        return 0
    fi
    if has_command fuser && fuser "$port/tcp" &>/dev/null; then
        return 0
    fi
    return 1
}

# Get PIDs listening on a port (deduped). Tries lsof → ss → fuser.
get_port_pids() {
    local port=$1
    local -a found=()
    local line pid

    if has_command lsof; then
        while read -r pid; do
            [[ -n "$pid" ]] && found+=("$pid")
        done < <(lsof -ti ":$port" -sTCP:LISTEN 2>/dev/null || true)
        if [[ ${#found[@]} -eq 0 ]]; then
            while read -r pid; do
                [[ -n "$pid" ]] && found+=("$pid")
            done < <(lsof -ti ":$port" 2>/dev/null || true)
        fi
    fi

    if [[ ${#found[@]} -eq 0 ]] && has_command ss; then
        while read -r line; do
            if [[ "$line" =~ pid=([0-9]+) ]]; then
                found+=("${BASH_REMATCH[1]}")
            fi
        done < <(ss -tlnp "( sport = :$port )" 2>/dev/null || true)
    fi

    if [[ ${#found[@]} -eq 0 ]] && has_command fuser; then
        while read -r pid; do
            [[ "$pid" =~ ^[0-9]+$ ]] && found+=("$pid")
        done < <(fuser "$port/tcp" 2>/dev/null | tr -s '[:space:]' '\n' || true)
    fi

    if [[ ${#found[@]} -eq 0 ]]; then
        echo ""
        return 0
    fi
    printf '%s\n' "${found[@]}" | sort -u | tr '\n' ' '
    echo
}

# Kill all processes on a port. Returns 0 if port is free afterwards.
kill_port() {
    local port=$1
    local pids
    local attempt
    pids=$(get_port_pids "$port" | xargs || true)

    if [[ -z "${pids// /}" ]]; then
        return 0
    fi

    log_warn "Port $port occupied — killing: $pids"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true

    for attempt in 1 2 3 4 5; do
        sleep 0.3
        if ! port_in_use "$port"; then
            return 0
        fi
        pids=$(get_port_pids "$port" | xargs || true)
        if [[ -n "${pids// /}" ]]; then
            # shellcheck disable=SC2086
            kill -9 $pids 2>/dev/null || true
        fi
    done

    if port_in_use "$port"; then
        log_error "Port $port still in use after kill: $(get_port_pids "$port")"
        return 1
    fi
    return 0
}

# Kill Vite / runserver processes that belong to THIS repo (not other projects).
kill_project_orphans() {
    local pattern
    # Match absolute paths under this workspace so we don't nuke unrelated Vite apps.
    pkill -9 -f "${FRONTEND_DIR}/node_modules/.bin/vite" 2>/dev/null || true
    pkill -9 -f "${FRONTEND_DIR}.*vite" 2>/dev/null || true
    pkill -9 -f "${BACKEND_DIR}/manage.py runserver" 2>/dev/null || true
    pkill -9 -f "manage.py runserver.*:${BACKEND_PORT}" 2>/dev/null || true
    pkill -9 -f "manage.py runserver.*0.0.0.0:${BACKEND_PORT}" 2>/dev/null || true
}

# Free canonical + spillover ports used in local dev.
clean_dev_ports() {
    local port
    local failed=0

    log_step "Killing project-scoped orphan Vite/runserver processes..."
    kill_project_orphans
    sleep 0.5

    log_step "Freeing backend port $BACKEND_PORT..."
    kill_port "$BACKEND_PORT" || failed=1

    log_step "Freeing frontend port $FRONTEND_PORT..."
    kill_port "$FRONTEND_PORT" || failed=1

    for port in "${FRONTEND_SPILL_PORTS[@]}"; do
        if port_in_use "$port"; then
            log_step "Freeing stray frontend spillover port $port..."
            kill_port "$port" || failed=1
        fi
    done

    # Stale PID files after forced kills
    rm -f "$PIDS_DIR"/*.pid 2>/dev/null || true

    return $failed
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

# Upsert KEY=VALUE into the frontend .env (add if missing, replace if present).
# Values may contain spaces/colons — we use a regex-escaped key match only.
fe_upsert() {
    local key="$1" value="$2" envfile="$FRONTEND_DIR/.env"
    touch "$envfile"
    if grep -qE "^${key}=" "$envfile" 2>/dev/null; then
        sed -i "s#^${key}=.*#${key}=${value}#" "$envfile"
    else
        echo "${key}=${value}" >> "$envfile"
    fi
}

# Upsert KEY=VALUE into the backend .env (add if missing, replace if present).
be_upsert() {
    local key="$1" value="$2" envfile="$BACKEND_DIR/.env"
    touch "$envfile"
    if grep -qE "^${key}=" "$envfile" 2>/dev/null; then
        sed -i "s#^${key}=.*#${key}=${value}#" "$envfile"
    else
        echo "${key}=${value}" >> "$envfile"
    fi
}

# Safely export every KEY=VALUE from an env file. Unlike `source`, this does
# NOT evaluate the value, so values containing # $ % @ * or spaces are safe.
# It also OVERRIDES any stale export already in the shell, which makes the
# .env file the single source of truth — Django's load_dotenv() only fills
# keys that are missing, so a lingering `export DJANGO_BRAND=aastmt` would
# otherwise pin the server to the WRONG brand/database/redis-db.
load_env_file() {
    local envfile="$1" line key value
    [[ -f "$envfile" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" ]] && continue                 # blank line
        [[ "$line" == \#* ]] && continue             # full-line comment
        key="${line%%=*}"
        [[ "$key" == "$line" ]] && continue          # no '=' → malformed
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        value="${line#*=}"
        value="${value%$'\r'}"                       # strip trailing CR
        # Strip one layer of surrounding quotes (python-dotenv style).
        case "$value" in
            \"*\"|\'*\') value="${value:1:${#value}-2}" ;;
        esac
        export "$key=$value"
    done < "$envfile"
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

    # backend/.env is the single source of truth (brand/DB/Redis/media/Pulse).
    # load_env_file already ran in main(); re-assert here for defense-in-depth
    # so a stale shell export can never pin the server to the wrong brand.
    load_env_file "$BACKEND_DIR/.env"

    # Start Django runserver WITHOUT StatReloader auto-reload by default.
    # StatReloader restarts the whole server on every .py edit; during active
    # development files change every few seconds, and each reload queues
    # in-flight requests ~13s (observed loan POST latency spike 4.3s -> 17.6s).
    # Set DJANGO_AUTORELOAD=1 to opt back into auto-reload for manual dev.
    local reload_flag="--noreload"
    if [[ "${DJANGO_AUTORELOAD:-0}" == "1" ]]; then
        reload_flag=""
    fi
    cd "$BACKEND_DIR" || return 1
    nohup "$python" manage.py runserver $reload_flag 0.0.0.0:$BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    
    # Verify (wait longer for AI models to load)
    log_info "Waiting for backend to be ready..."
    sleep 8
    
    # Check if port is open AND API responds
    if port_in_use "$BACKEND_PORT"; then
        # Try to hit health endpoint
        if curl -s --max-time 5 "http://localhost:$BACKEND_PORT${DJANGO_API_PREFIX}health/" > /dev/null 2>&1; then
            log_success "Backend started (PID: $(cat "$BACKEND_PID"), Port: $BACKEND_PORT)"
            return 0
        else
            log_warn "Backend port open but API not responding yet (may still be loading)"
            return 0  # Don't fail, just warn
        fi
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
    # Vite reads .env itself, but a stale VITE_* export in the shell would take
    # precedence — re-export the file so local .env is the source of truth.
    load_env_file "$FRONTEND_DIR/.env"
    export PORT="$FRONTEND_PORT"
    export VITE_PORT="$FRONTEND_PORT"
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
    
    # Check and start Redis
    if redis-cli ping &>/dev/null; then
        log_success "Redis running"
    else
        log_warn "Redis not running - starting..."
        redis-server --daemonize yes &>/dev/null && sleep 1
        if redis-cli ping &>/dev/null; then
            log_success "Redis started"
        else
            log_warn "Could not start Redis automatically"
        fi
    fi
    
    if [[ "$deps_ok" == false ]]; then
        log_error "Missing dependencies. Cannot start."
        return 1
    fi
    
    echo ""
    log_info "Starting services..."
    echo ""
    
    local all_ok=true

    # Read-only superuser check — does NOT seed or create any users.
    # (Superusers already exist in the pulled prod data. To create one on a
    #  fresh DB, use: ./manage.sh createsuperuser)
    local python
    python=$(get_python)
    if [[ -n "$python" ]]; then
        local su_count
        # Django prints "N objects imported automatically" to stdout, which
        # would break a bare numeric capture — use a marker and grep it out.
        su_count=$(cd "$BACKEND_DIR" && "$python" manage.py shell -c \
            "from django.contrib.auth import get_user_model as _U; print('__SU_COUNT__=' + str(_U().objects.filter(is_superuser=True, is_active=True).count()))" 2>/dev/null \
            | grep -oE '__SU_COUNT__=[0-9]+' | cut -d'=' -f2)
        if [[ "$su_count" =~ ^[0-9]+$ ]] && [[ "$su_count" -gt 0 ]]; then
            log_success "Superuser check: $su_count active admin account(s) present"
        else
            log_warn "No active superuser found. Create one with: ./manage.sh createsuperuser"
        fi
    fi

    start_backend || all_ok=false
    start_frontend || all_ok=false
    
    echo ""
    if [[ "$all_ok" == true ]]; then
        log_success "All services started!"
        echo ""
        echo -e "  ${CYAN}Frontend:${NC}  ${GREEN}$(frontend_public_url)${NC}"
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
    
    # Free ports + kill orphans (WSL-safe; covers spillover 5180+)
    clean_dev_ports || true
    
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
        echo -e "  $(printf '%-18s' '') ${CYAN}http://localhost:$BACKEND_PORT${DJANGO_API_PREFIX}${NC}"
        echo -e "  $(printf '%-18s' '') ${CYAN}http://localhost:$BACKEND_PORT/swagger/${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    # Frontend
    local frontend_pid
    frontend_pid=$(read_pid "$FRONTEND_PID")
    printf "  %-18s" "Frontend:"
    if pid_running "$frontend_pid" && port_in_use "$FRONTEND_PORT"; then
        echo -e "${GREEN}RUNNING${NC} (PID: $frontend_pid, Port: $FRONTEND_PORT)"
        echo -e "  $(printf '%-18s' '') ${CYAN}$(frontend_public_url)${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo ""
    log_info "Infrastructure"
    echo ""

    local _brand
    _brand=$(grep -E '^DJANGO_BRAND=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d '[:space:]')
    _brand=${_brand:-aastmt}
    printf "  %-18s" "Brand:"
    echo -e "${MAGENTA}${_brand}${NC}"

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
    frontend_response=$(curl -sf -o /dev/null -w "%{http_code}" "$(frontend_public_url)" 2>/dev/null || echo "000")
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

# ── Brand switch (multi-DB dev isolation) ─────────────────────────────────
# Each brand has its OWN Postgres DB (aastmt→carbon_dev, nibras→nibras_dev,
# medos→medos_dev, tectona→tectona_dev), derived in config/settings.py from
# DJANGO_BRAND. The frontend has per-instance env files (.env.instance.<id>).
cmd_brand() {
    local brand="${1:-}"
    local -a BRAND_IDS=(aastmt nibras medos tectona)

    # Mirrors BRAND_DB_NAMES in backend/config/settings.py
    local -A BRAND_DB=(
        [aastmt]=carbon_dev
        [nibras]=nibras_dev
        [medos]=medos_dev
        [tectona]=tectona_dev
    )

    # Per-brand Redis DB index (isolates Django cache + Pulse ephemeral memory).
    local -A BRAND_REDIS_DB=(
        [aastmt]=0
        [nibras]=1
        [medos]=2
        [tectona]=3
    )

    # Backend branding — mirrors carbon-frontend/src/brands/*.js (single source
    # of truth). Drives emails/PDFs/API docs + PLATFORM_TITLE on the backend.
    local -A BRAND_PLATFORM_NAME=(
        [aastmt]="Data Trust Platform"
        [nibras]="Nibras"
        [medos]="medOS"
        [tectona]="Tectona"
    )
    local -A BRAND_PLATFORM_SHORT=(
        [aastmt]="Data Trust"
        [nibras]="نبراس"
        [medos]="medOS"
        [tectona]="Tectona"
    )
    local -A BRAND_INSTANCE_NAME=(
        [aastmt]="AASTMT"
        [nibras]="Nibras"
        [medos]="ClearTurn"
        [tectona]="ClearTurn"
    )

    local current
    current=$(grep -E '^DJANGO_BRAND=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d '[:space:]')
    current=${current:-aastmt}

    if [[ -z "$brand" ]]; then
        print_header
        log_info "Current brand: ${MAGENTA}${current}${NC}  (DB: ${BRAND_DB[$current]:-${current}_dev})"
        echo ""
        for b in "${BRAND_IDS[@]}"; do
            if [[ "$b" == "$current" ]]; then
                echo -e "  ${GREEN}✓${NC} ${MAGENTA}${b}${NC}  →  ${BRAND_DB[$b]:-${b}_dev}"
            else
                echo -e "    ${b}  →  ${BRAND_DB[$b]:-${b}_dev}"
            fi
        done
        echo ""
        log_info "Switch with: ./manage.sh brand <id>"
        return 0
    fi

    local valid=""
    for b in "${BRAND_IDS[@]}"; do
        [[ "$b" == "$brand" ]] && valid=1
    done
    if [[ -z "$valid" ]]; then
        log_error "Unknown brand '$brand'. Valid: ${BRAND_IDS[*]}"
        return 1
    fi

    print_header
    log_info "Switching brand → ${MAGENTA}${brand}${NC} (DB: ${BRAND_DB[$brand]:-${brand}_dev})"
    echo ""

    # 1) Backend: flip brand + all per-brand runtime scoping so switching is
    # leak-free. (DB name is derived from DJANGO_BRAND in settings.py.)
    log_step "Updating backend/.env (brand, DB, Redis, media, Pulse, branding)"
    be_upsert "DJANGO_BRAND" "$brand"
    be_upsert "PULSE_INSTANCE_ID" "$brand"
    be_upsert "REDIS_URL" "redis://localhost:6379/${BRAND_REDIS_DB[$brand]}"
    be_upsert "DJANGO_MEDIA_ROOT" "./mediafiles/${brand}/"
    be_upsert "DATASCHEMA_UPLOAD_PATH" "dataschema_uploads/${brand}/"
    be_upsert "CHROMA_PERSIST_DIR" "./chroma_db/${brand}"
    be_upsert "DJANGO_PLATFORM_NAME" "${BRAND_PLATFORM_NAME[$brand]}"
    be_upsert "DJANGO_PLATFORM_SHORT" "${BRAND_PLATFORM_SHORT[$brand]}"
    be_upsert "DJANGO_INSTANCE_NAME" "${BRAND_INSTANCE_NAME[$brand]}"
    # Ensure the brand's media/upload/chroma dirs exist so Django never falls
    # back to a shared location.
    mkdir -p "$BACKEND_DIR/mediafiles/$brand" "$BACKEND_DIR/dataschema_uploads/$brand" "$BACKEND_DIR/chroma_db/$brand" 2>/dev/null || true
    log_success "backend/.env → DJANGO_BRAND=${brand}, PULSE_INSTANCE_ID=${brand}, REDIS_URL=…/${BRAND_REDIS_DB[$brand]}"

    # 2) Frontend: copy ONLY branding keys from the preset, preserving the
    # local API URL. (The presets point at production; a raw `cp` would make
    # the local frontend talk to the live backend.)
    local fe="${FRONTEND_DIR}/.env.instance.${brand}"
    if [[ -f "$fe" ]]; then
        log_step "Applying brand '${brand}' to frontend env (local API URL preserved)"
        local -a FE_KEYS=(VITE_BRAND VITE_PLATFORM_NAME VITE_PLATFORM_SHORT VITE_PLATFORM_TITLE VITE_PLATFORM_TAGLINE VITE_PLATFORM_DESCRIPTION VITE_INSTANCE_NAME VITE_PULSE_INSTANCE_ID)
        local k v
        for k in "${FE_KEYS[@]}"; do
            v=$(grep -E "^${k}=" "$fe" 2>/dev/null | head -1 | cut -d'=' -f2-)
            [[ -n "$v" ]] && fe_upsert "$k" "$v"
        done
        # Local dev always talks to the local backend/frontend.
        fe_upsert "VITE_API_BASE_URL" "http://localhost:${BACKEND_PORT}/carbon-api/"
        fe_upsert "VITE_CANONICAL_URL" "http://localhost:${FRONTEND_PORT}"
        log_success "carbon-frontend/.env → VITE_BRAND=${brand} (local API URL preserved)"
    else
        log_warn "No $fe — leaving carbon-frontend/.env unchanged"
    fi

    echo ""
    log_success "Brand switched to '${brand}' (DB: ${BRAND_DB[$brand]:-${brand}_dev})."
    log_info "Run './manage.sh restart' to apply. DB already provisioned if you ran the one-time setup."
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

# W6-E F-29: materialize due plan schedules into reviewable Runs (idempotent).
# Cron (manual/CI-only; NO docker):
#   */5 * * * * cd /home/ahmed/aast/carbon && ./manage.sh schedules >> logs/schedules.log 2>&1
# Preview first with:  ./manage.sh schedules --dry-run
cmd_schedules() {
    print_header
    log_info "Running due plan schedules..."
    echo ""

    local python
    python=$(get_python)

    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi

    cd "$BACKEND_DIR" || return 1
    if [[ "${1:-}" == "--dry-run" ]]; then
        "$python" manage.py run_due_schedules --dry-run
    else
        "$python" manage.py run_due_schedules
    fi
}

# Pulse Heartbeat (P1b): proactive/consolidation/distill/decay loops + telemetry.
# Cron (manual/CI-only; NO docker):
#   0 2 * * * cd /home/ahmed/aast/carbon && ./manage.sh maintenance >> logs/maintenance.log 2>&1
# Preview first with:  ./manage.sh maintenance --dry-run
cmd_maintenance() {
    print_header
    log_info "Running Pulse maintenance (heartbeat)..."
    echo ""

    local python
    python=$(get_python)

    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi

    cd "$BACKEND_DIR" || return 1
    "$python" manage.py ensure_pulse_instance

    # Build args, omitting empties so argparse never sees a stray "" positional.
    local -a maint_args=()
    local loops_arg
    if [[ "${1:-}" == "--dry-run" ]]; then
        maint_args+=(--dry-run)
        loops_arg="${2:-}"
    else
        loops_arg="${1:-}"
    fi
    [[ -n "$loops_arg" ]] && maint_args+=(--loops "$loops_arg")

    "$python" manage.py run_pulse_maintenance "${maint_args[@]}"
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

cmd_createsuperuser() {
    local python
    python=$(get_python)
    
    if [[ -z "$python" ]]; then
        log_error "Python venv not found!"
        return 1
    fi
    
    cd "$BACKEND_DIR" || return 1
    "$python" manage.py createsuperuser
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

cmd_clean_ports() {
    print_header
    log_info "Cleaning local-dev ports (backend $BACKEND_PORT, frontend $FRONTEND_PORT + spillover)..."
    echo ""

    if clean_dev_ports; then
        echo ""
        log_success "Ports are free"
        log_info "Backend  :$BACKEND_PORT  Frontend :$FRONTEND_PORT  (spillover 5180–5185 cleared if held)"
        echo ""
        # Show residual listeners for these ports (should be empty)
        local port
        for port in "$BACKEND_PORT" "$FRONTEND_PORT" "${FRONTEND_SPILL_PORTS[@]}"; do
            if port_in_use "$port"; then
                log_warn "Still listening on :$port → PIDs: $(get_port_pids "$port")"
            fi
        done
    else
        echo ""
        log_error "Some ports could not be freed — see warnings above"
        exit 1
    fi
}

cmd_killall() {
    print_header
    log_warn "EMERGENCY: Force killing all Carbon processes..."
    echo ""

    log_step "Killing tracked services..."
    kill_service "Frontend" "$FRONTEND_PID" || true
    kill_service "Backend" "$BACKEND_PID" || true

    log_step "Cleaning ports + project orphans..."
    clean_dev_ports || true

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
    echo "  createsuperuser    Create a Django superuser (interactive)"
    echo "  brand [id]         Show current brand, or switch (aastmt|nibras|medos|tectona)"
    echo "  test               Run backend tests (pytest)"
    echo "  schedules [--dry-run]  Materialize due plan schedules (W6-E F-29)"
    echo "  maintenance [--dry-run] [--loops]  Pulse heartbeat: consolidate/distill/decay"
    echo "  clean              Deep clean (stop, clear caches, archive logs)"
    echo "  clean-ports        Force-free :$BACKEND_PORT / :$FRONTEND_PORT (+ Vite spillover 5180–5185)"
    echo "  killall            Emergency: force kill everything"
    echo "  help               Show this help"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  ./manage.sh start          # Start everything"
    echo "  ./manage.sh stop           # Stop everything"
    echo "  ./manage.sh clean-ports    # Kill whatever is holding the ports"
    echo "  ./manage.sh status         # Check what's running"
    echo "  ./manage.sh logs backend   # View backend logs"
    echo "  ./manage.sh migrate        # Run DB migrations"
    echo "  ./manage.sh schedules      # Fire due plan schedules (cron: */5 * * * *)"
    echo "  ./manage.sh maintenance    # Pulse heartbeat (cron: 0 2 * * *)"
    echo "  ./manage.sh clean          # Full cleanup"
    echo ""
    echo -e "${CYAN}Ports:${NC}"
    echo "  Backend:   http://localhost:$BACKEND_PORT"
    echo "  Frontend:  $(frontend_public_url)"
    echo "  (Vite strictPort — if you see :5180, run clean-ports; do not use the spillover URL)"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    setup_dirs

    # backend/.env is the single source of truth for every Django command
    # (start, migrate, shell, test, schedules, createsuperuser, …). Load it
    # here so a stale `export` in the caller's shell can never leak the wrong
    # brand/DB/Redis/Pulse into any child process.
    load_env_file "$BACKEND_DIR/.env"

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
        createsuperuser) cmd_createsuperuser ;;
        brand)      cmd_brand "${2:-}" ;;
        test)       cmd_test "$@" ;;
        schedules)  cmd_schedules "${2:-}" ;;
        maintenance) cmd_maintenance "${2:-}" "${3:-}" ;;
        clean)      cmd_clean ;;
        clean-ports|clean_ports|ports) cmd_clean_ports ;;
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
