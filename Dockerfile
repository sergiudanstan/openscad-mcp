FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MCP_TRANSPORT=streamable-http \
    PORT=7860 \
    HOME=/home/app

# OpenSCAD CLI + Xvfb (PNG previews need an X display even in CLI mode)
# libgl1, libegl1, libgles2 cover the EGL/GL stack OpenSCAD pulls in
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        openscad \
        xvfb \
        ca-certificates \
        libgl1 \
        libegl1 \
        libgles2 \
 && rm -rf /var/lib/apt/lists/*

# Wrap openscad so every invocation gets a virtual X display.
# Place shim at /usr/local/bin/openscad (earlier in PATH than /usr/bin/openscad).
RUN printf '#!/bin/sh\nexec xvfb-run -a /usr/bin/openscad "$@"\n' > /usr/local/bin/openscad \
 && chmod +x /usr/local/bin/openscad

# Non-root user with a real $HOME so the workspace path
# (~/openscad-mcp-workspace) is writeable.
RUN useradd --create-home --home-dir /home/app --shell /bin/sh app
WORKDIR /home/app/openscad-mcp

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./
RUN pip install --no-cache-dir .

RUN chown -R app:app /home/app
USER app

EXPOSE 7860

CMD ["python", "-m", "openscad_mcp"]
