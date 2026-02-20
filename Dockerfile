FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p nanobot bridge && touch nanobot/__init__.py && \
    uv pip install --system --no-cache ".[all-channels]" && \
    rm -rf nanobot bridge

# Copy the full source and install
COPY nanobot/ nanobot/
COPY bridge/ bridge/
RUN uv pip install --system --no-cache ".[all-channels]"

# Create config directory
RUN mkdir -p /root/.nanobot

# Gateway default port
EXPOSE 18790

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD nanobot status || exit 1

ENTRYPOINT ["nanobot"]
CMD ["gateway"]
