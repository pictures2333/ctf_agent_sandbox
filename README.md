# ctf-agent-sandbox

Python package for building and running your CTF sandbox with Docker SDK.

## Use as CLI tool

1. Load required host kernel modules:

```bash
./setup.sh
```

2. Install deps:

```bash
uv sync
```

3. Generate artifacts from config:

```bash
uv run ctf-agent-sandbox --config config.example.json --output-dir .
```

Use module entrypoint if needed:

```bash
uv run -m ctf_agent_sandbox --config config.example.json --output-dir .
```

## Use as module

### Import API

```python
from ctf_agent_sandbox import build_image, run_container, stop_container
```

- `build_image(config)`  
Builds the image and writes state to `.sandbox_state.json`.

- `run_container(config=None)`  
Runs a container from stored state (or overridden config) and returns container ID.

- `stop_container(container_id)`  
Stops and removes the container.

### Add as dependency (from another project)

```toml
[tool.uv.sources]
ctf-agent-sandbox = { path = "../ctf_agent_sandbox" }
```

### Config

Use [config.example.json](/home/p23/develope/Agent-CTF-Bot_I-love-suisei/src/ctf_agent_sandbox/config.example.json) as template.

Key sections:
- `services`: background service entries with `name` + `options`
  - for `mcp-terminal`, options include `host_path`, `container_path`, `skill_path`
- background service plugins are managed under `background_services/`
- `ai-cli-tools`: `codex`, `gemini`, `opencode`
- `packages`: grouped by `name`
- tool auth/config host paths (default `~/.xxx`)
- workspace/image paths and `container_name_prefix` (runtime generates unique container names)

## Skills behavior

- Shared skills come from `skills`.
- Sandbox environment hint skill is auto-generated on each `build_image` and auto-mounted.
- `mcp-terminal` skill is mounted only when a `services` item has `name: mcp-terminal`.
