# ctf_agent_sandbox

Build/run CTF sandbox containers with Docker SDK.

## CLI

```bash
# Host prerequisites
./setup.sh

# Install dependencies
uv sync
```

```bash
# Generate Dockerfile/startup/state template (no image build)
uv run -m ctf_agent_sandbox assemble \
  --config config.example.yaml \
  --output-dir . \
  --state-file ./.sandbox_state.json

# Build image and persist image_id into state file
uv run -m ctf_agent_sandbox build-image --config config.example.yaml

# Build image with Docker build logs
uv run -m ctf_agent_sandbox build-image --config config.example.yaml --verbose

# Run container from state file
uv run -m ctf_agent_sandbox run-container

# Stop and remove one container by id
uv run -m ctf_agent_sandbox stop-container --container-id <container_id>
```

If console script is installed:

```bash
# Same as `-m` entrypoint, using console script
uv run ctf_agent_sandbox assemble \
  --config config.example.yaml \
  --output-dir . \
  --state-file ./.sandbox_state.json
```

## Module

```toml
[tool.uv.sources]
ctf_agent_sandbox = { path = "../ctf_agent_sandbox" }
```

```python
from ctf_agent_sandbox import build_image, run_container, stop_container
```

- `assemble_and_write(config, ...)` writes Dockerfile/startup/state template
  (`image_id: null`, `run_params`).
- `build_image(config)` writes `.sandbox_state.json` (image id + run params).
- `run_container(...)` runs from state and returns container id.
- `stop_container(container_id)` stops/removes container.

## Config

Template: [config.example.yaml](./config.example.yaml)

Main keys:
- `services`: background services (`name` + `options`)
- `agent-cli-tools`: tool plugins (`name` + `options`)
- `prompt_file`: prompt source file, mounted only when each tool sets
  `options.prompt_filename`
- `packages`: package groups
- `custom_install_commands`: custom install commands (`run_as: root|agent`)
- `startup_script_host_path`: generated runtime startup path (use `.sandbox_generated/...`, keep template files untouched)

## Templates
- `templates/Dockerfile.tpl`
- `templates/startup.sh.tpl`
- `templates/env-skill.md.tpl`