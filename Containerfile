FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /build

# Ensure Python output is unbuffered and bytecode is not written
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

# Copy package manifests first for optimal layer caching
COPY requirements.txt pyproject.toml /build/
COPY modules/core/pyproject.toml /build/modules/core/
COPY modules/shared/pyproject.toml /build/modules/shared/
COPY modules/mcp/pyproject.toml /build/modules/mcp/
COPY modules/cli/pyproject.toml /build/modules/cli/

# Install base dependencies and testing toolchain
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

