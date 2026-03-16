#!/bin/sh

sudo chown -R agent:agent /home/agent/.codex
sudo chown -R agent:agent /home/agent/.local

sudo dockerd &

/bin/sh /mcp/mcp_run.sh &

cd /home/agent/challenge || exit 1

/home/agent/.opencode/bin/opencode serve --hostname 0.0.0.0 --port 4096 &

tail -f /dev/null