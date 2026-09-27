FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /build

# Ensure Python output is unbuffered and bytecode is not written
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

# Copy package manifests first for optimal layer caching
COPY requirements.txt pyproject.toml /build/
COPY modules/shared/pyproject.toml /build/modules/shared/
COPY modules/mcp/pyproject.toml /build/modules/mcp/
COPY modules/cli/pyproject.toml /build/modules/cli/

# Install base dependencies and testing toolchain. The base image tag must track
# the Playwright version pinned in uv.lock: the image ships the matching
# chromium and chrome-headless-shell revisions under /ms-playwright, and every
# --headless launch fails if those revisions drift from the installed driver.
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pytest pytest-mock ruff

# Copy full codebase, install pure standalone wheel, and clean build directory
COPY . /build
RUN pip install --no-cache-dir . && rm -rf /build

# Create standard XDG directories and set workdir to /root
RUN mkdir -p /root/.local/share/qwen-web /root/.local/state/qwen-web /root/.config/qwen-web
WORKDIR /root

# Default entrypoint to qwa (qwen-web-arwaky)
ENTRYPOINT ["qwa"]
CMD ["--help"]
