#!/usr/bin/env bash
set -euo pipefail

sudo chown -R agent:agent /home/agent/.local
sudo chown -R agent:agent /home/agent/.codex
sudo chown -R agent:agent /home/agent/.gemini

{{STARTUP_COMMANDS}}
tail -f /dev/null
