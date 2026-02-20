#!/usr/bin/env bash
set -euo pipefail

# nanobot management script — simplifies Docker Compose operations

COMPOSE_FILE="docker-compose.yml"

# --- helpers ---

die() { echo "Error: $1" >&2; exit 1; }

check_deps() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed"
    docker compose version >/dev/null 2>&1 || die "docker compose is not available"
}

service_exists() {
    docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -qx "$1"
}

require_service() {
    [ -n "${1:-}" ] || die "service name is required"
    service_exists "$1" || die "service '$1' not found in $COMPOSE_FILE"
}

# --- commands ---

cmd_build() {
    docker compose -f "$COMPOSE_FILE" build "$@"
}

cmd_start() {
    if [ $# -eq 0 ]; then
        docker compose -f "$COMPOSE_FILE" up -d
    else
        require_service "$1"
        docker compose -f "$COMPOSE_FILE" up -d "$1"
    fi
}

cmd_stop() {
    if [ $# -eq 0 ]; then
        docker compose -f "$COMPOSE_FILE" stop
    else
        require_service "$1"
        docker compose -f "$COMPOSE_FILE" stop "$1"
    fi
}

cmd_restart() {
    if [ $# -eq 0 ]; then
        docker compose -f "$COMPOSE_FILE" stop
        docker compose -f "$COMPOSE_FILE" up -d
    else
        require_service "$1"
        docker compose -f "$COMPOSE_FILE" stop "$1"
        docker compose -f "$COMPOSE_FILE" up -d "$1"
    fi
}

cmd_logs() {
    if [ $# -eq 0 ]; then
        docker compose -f "$COMPOSE_FILE" logs -f
    else
        require_service "$1"
        docker compose -f "$COMPOSE_FILE" logs -f "$1"
    fi
}

cmd_status() {
    docker compose -f "$COMPOSE_FILE" ps
}

cmd_onboard() {
    require_service "$1"
    docker compose -f "$COMPOSE_FILE" run --rm "$1" onboard
}

cmd_cli() {
    [ $# -ge 2 ] || die "usage: $0 cli <service> <message>"
    require_service "$1"
    local service="$1"
    shift
    docker compose -f "$COMPOSE_FILE" run --rm "$service" agent -m "$*"
}

cmd_reset() {
    require_service "$1"
    local workspace="nano_config/$1/workspace"
    echo "This will DELETE '$workspace' and re-run onboard for '$1'."
    echo "Your config.json (API keys) will be preserved."
    read -p "Are you sure? [y/N] " confirm
    [[ "$confirm" =~ ^[yY]$ ]] || { echo "Aborted."; exit 0; }
    rm -rf "$workspace"
    echo "Removed $workspace"
    docker compose -f "$COMPOSE_FILE" run --rm "$1" onboard
    echo "Onboard complete for '$1'."
}

cmd_help() {
    cat <<'EOF'
nanobot management script

Usage: ./nanobot.sh <command> [args]

Commands:
  build                   Build the Docker image
  start [service]         Start services (all if no service specified)
  stop [service]          Stop services (all if no service specified)
  restart [service]       Restart services (all if no service specified)
  logs [service]          Follow logs (all if no service specified)
  status                  Show running containers
  onboard <service>       Run first-time setup for a service
  cli <service> <msg>     Send a message to a service's agent
  reset <service>         Remove workspace and re-onboard (preserves config.json)
  help                    Show this help

Examples:
  ./nanobot.sh build                        # Build the image
  ./nanobot.sh onboard alice                # First-time setup for alice
  ./nanobot.sh start alice                  # Start alice in background
  ./nanobot.sh start                        # Start all services
  ./nanobot.sh logs alice                   # Follow alice's logs
  ./nanobot.sh cli alice "Hello!"           # Send a message to alice
  ./nanobot.sh restart bob                  # Restart bob
  ./nanobot.sh reset alice                  # Wipe alice's workspace and re-onboard
EOF
}

# --- main ---

check_deps

case "${1:-help}" in
    build)   shift; cmd_build "$@" ;;
    start)   shift; cmd_start "$@" ;;
    stop)    shift; cmd_stop "$@" ;;
    restart) shift; cmd_restart "$@" ;;
    logs)    shift; cmd_logs "$@" ;;
    status)  shift; cmd_status "$@" ;;
    onboard) shift; cmd_onboard "$@" ;;
    cli)     shift; cmd_cli "$@" ;;
    reset)   shift; cmd_reset "$@" ;;
    help|--help|-h) cmd_help ;;
    *)       die "unknown command: $1 (try './nanobot.sh help')" ;;
esac
