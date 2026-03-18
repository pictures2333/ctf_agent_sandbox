#!/usr/bin/env bash
set -euo pipefail

sudo chown -R agent:agent /home/agent/.local    || echo "failed to change permission of /home/agent/.local"
sudo chown -R agent:agent /home/agent/.codex    || echo "failed to change permission of /home/agent/.codex"
sudo chown -R agent:agent /home/agent/.gemini   || echo "failed to change permission of /home/agent/.gemini"

{{STARTUP_COMMANDS}}
tail -f /dev/null
