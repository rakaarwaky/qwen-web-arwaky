#!/usr/bin/env bash
# Helper script to build and run qwen-web-arwaky (qwa) in an isolated Podman container.
set -euo pipefail

IMAGE_NAME="qwen-web-arwaky"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VOLUME_DIR="/home/raka/.local/share/containers/storage/volumes/qwen-web-arwaky/_data"
mkdir -p "${VOLUME_DIR}/share" "${VOLUME_DIR}/state" "${VOLUME_DIR}/config" "${VOLUME_DIR}/finding"

VOLUMES="-v ${VOLUME_DIR}/share:/root/.local/share/qwen-web:Z \
         -v ${VOLUME_DIR}/state:/root/.local/state/qwen-web:Z \
         -v ${VOLUME_DIR}/config:/root/.config/qwen-web:Z \
         -v "${REPO_ROOT}/.agents/finding:/root/.local/share/qwen-web/finding:Z""
GUI_ENV="-e DISPLAY=${DISPLAY:-:0} -v /tmp/.X11-unix:/tmp/.X11-unix:ro --net=host"

CONTAINER_NAME="qwen-web-arwaky"

is_running() {
    podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

container_exists() {
    podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

recreate_container() {
    if container_exists; then
        echo "==> Removing old container '${CONTAINER_NAME}' to use new image (volumes & login session are preserved)..."
        podman rm -f "${CONTAINER_NAME}" >/dev/null
    fi
    start_container
}

start_container() {
    if is_running; then
        return 0
    fi
    if container_exists; then
        echo "==> Starting existing container '${CONTAINER_NAME}'..."
        podman start "${CONTAINER_NAME}" >/dev/null
    else
        echo "==> Spawning persistent container '${CONTAINER_NAME}'..."
        podman run -d \
            --name "${CONTAINER_NAME}" \
            --shm-size=2g \
            ${GUI_ENV} \
            ${VOLUMES} \
            --entrypoint sleep \
            "${IMAGE_NAME}" infinity >/dev/null
    fi
}

usage() {
    cat <<EOF
Usage: $0 [command] [args...]

Commands:
  start                 Start persistent container in background (visible in Podman Desktop)
  stop                  Stop the persistent container
  status                Show status of persistent container
  login                 Open browser in container to login to Qwen (saves session to Podman volume)
  doctor                Run doctor diagnostics inside container
  prompt "text"         Run a direct prompt headlessly using saved login session
  run [args...]         Run any qwa command inside container (e.g. $0 run --help)
  shell                 Open an interactive bash shell inside the container
  test                  Run full pytest unit/integration test suite inside container
  lint                  Run ruff lint check inside container
  build                 Build/rebuild image AND recreate container with new image (${IMAGE_NAME})
  help                  Show this help message
EOF
}

cmd="${1:-help}"

TTY_FLAGS=""
if [ -t 0 ] && [ -t 1 ]; then
    TTY_FLAGS="-it"
else
    TTY_FLAGS="-i"
fi

case "$cmd" in
    start)
        start_container
        echo "==> Container '${CONTAINER_NAME}' is RUNNING and visible in Podman Desktop!"
        ;;
    stop)
        if is_running; then
            echo "==> Stopping container '${CONTAINER_NAME}'..."
            podman stop "${CONTAINER_NAME}" >/dev/null
            echo "==> Container stopped."
        else
            echo "==> Container '${CONTAINER_NAME}' is not running."
        fi
        ;;
    status)
        podman ps -a --filter "name=^${CONTAINER_NAME}$"
        ;;
    build)
        echo "==> Building Podman image: ${IMAGE_NAME}..."
        podman build -t "${IMAGE_NAME}" -f "${REPO_ROOT}/Containerfile" "${REPO_ROOT}"
        echo "==> Image '${IMAGE_NAME}' successfully built!"
        # Recreate the container so it runs the freshly built image.
        # Without this, 'podman start' on the old container keeps using the OLD image.
        recreate_container
        ;;
    login)
        echo "==> Authorizing local X11 display connection..."
        xhost +local:root 2>/dev/null || xhost +local: 2>/dev/null || true
        start_container
        echo "==> Opening headed browser in Podman for Qwen login..."
        podman exec ${TTY_FLAGS} -e DISPLAY="${DISPLAY:-:0}" "${CONTAINER_NAME}" qwa login "${@:2}"
        ;;
    doctor)
        start_container
        echo "==> Running doctor health checks in Podman..."
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" qwa doctor "${@:2}"
        ;;
    test)
        start_container
        echo "==> Running pytest test suite inside Podman..."
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" pytest tests/ -m "not e2e and not slow" "${@:2}"
        ;;
    lint)
        start_container
        echo "==> Running ruff inside Podman..."
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" ruff check modules/ tests/ "${@:2}"
        ;;
    shell)
        start_container
        echo "==> Opening interactive shell in container..."
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" bash
        ;;
    prompt)
        if [ -z "${2:-}" ]; then
            echo "Error: Prompt text required. Example: $0 prompt 'Hello world'"
            exit 1
        fi
        start_container
        echo "==> Running prompt inside Podman..."
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" qwa prompt-direct -t "$2" --headless "${@:3}"
        ;;
    run)
        start_container
        podman exec ${TTY_FLAGS} "${CONTAINER_NAME}" qwa "${@:2}"
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Unknown command: $cmd"
        usage
        exit 1
        ;;
esac

