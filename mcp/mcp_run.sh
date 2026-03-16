#!/bin/sh

# mcp terminal
$(
cd /mcp/mcp_terminal &&
uv sync &&
uv run main.py --host 127.0.0.1 --port 8000 --path /mcp --workdir /home/agent/challenge --shell /bin/bash
) &