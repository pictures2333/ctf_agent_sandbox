# ctf_agent_sandbox

Build/run CTF sandbox containers with Docker SDK.

Default `work_dir` is `./.sandbox_workdir` (to avoid polluting repository root).

## CLI

```bash
# Host prerequisites
./setup.sh

# Install dependencies
uv sync
```

```bash
# Assemble in memory and print JSON (no file output)
uv run -m ctf_agent_sandbox assemble \
  --config config.example.yaml \
  --work-dir ./test2

# Generate Dockerfile/startup/state template (no image build)
uv run -m ctf_agent_sandbox assemble-and-write \
  --config config.example.yaml \
  --work-dir ./test2

# Build image and persist image_id into state file
uv run -m ctf_agent_sandbox build-image \
  --config config.example.yaml \
  --work-dir ./test2

# Build image with Docker build logs
uv run -m ctf_agent_sandbox build-image \
  --config config.example.yaml \
  --work-dir ./test2 \
  --verbose

# Run container from state file
uv run -m ctf_agent_sandbox run-container --work-dir ./test2

# Stop and remove one container by id
uv run -m ctf_agent_sandbox stop-container --container-id <container_id>
```

If console script is installed:

```bash
# Same as `-m` entrypoint, using console script
uv run ctf_agent_sandbox assemble \
  --config config.example.yaml \
  --work-dir ./test2

uv run ctf_agent_sandbox assemble-and-write \
  --config config.example.yaml \
  --work-dir ./test2
```

## Module

```toml
[tool.uv.sources]
ctf_agent_sandbox = { path = "../ctf_agent_sandbox" }
```

```python
from ctf_agent_sandbox import assemble, assemble_and_write, build_image, run_container, stop_container
```

```python
config = {...}  # dict or SandboxConfig
work_dir = "./test2"  # default is ./.sandbox_workdir

# In-memory only (no file output).
result = assemble(config, work_dir=work_dir)

# Write Dockerfile/startup/state template into work_dir.
assemble_and_write(config, work_dir=work_dir)

# Build image and write work_dir/.state.json.
image_id = build_image(config, work_dir=work_dir, verbose=True)

# Run from work_dir/.state.json and return container id.
container_id = run_container(work_dir=work_dir)

# Stop/remove container by id.
stop_container(container_id)
```

- `assemble(config, work_dir=...)`: returns `AssemblyResult` only.
- `assemble_and_write(config, work_dir=...)`: writes `<work_dir>/Dockerfile`,
  `<work_dir>/script/startup.sh`, `<work_dir>/.state.json` (`image_id: null`).
- `build_image(config, ..., work_dir=...)`: writes `<work_dir>/.state.json`
  (`image_id` + `run_params`) and returns `image_id`.
- `run_container(work_dir=...)`: reads `<work_dir>/.state.json` and returns `container_id`.
- `stop_container(container_id)`: stops/removes container.

## Config

Template: [config.example.yaml](./config.example.yaml)

`config` input path is independent from `work_dir` (use `--config` to select input file).

Main keys:
- `services`: background services (`name` + `options`)
- `agent-cli-tools`: tool plugins (`name` + `options`)
- `prompt_file`: prompt source file, mounted only when each tool sets
  `options.prompt_filename`
- `packages`: package groups
- `custom_install_commands`: custom install commands (`run_as: root|agent`)
- `startup_script_host_path`: generated runtime startup path (use `.sandbox_generated/...`, keep template files untouched)

## Templates
- `templates/` only stores source templates. Do not edit generated files as templates.
- `templates/Dockerfile.tpl`: base template for rendered `Dockerfile`.
- `templates/startup.sh.tpl`: base template for rendered runtime startup script.
- `templates/env-skill.md.tpl`: base template for auto-generated sandbox environment skill.
- Rendered outputs are written to:
  - `assemble-and-write --work-dir <dir>`: `<dir>/Dockerfile`, `<dir>/script/startup.sh`, `<dir>/.state.json`
  - runtime bind path: `<work_dir>/<startup_script_host_path>` when configured as relative path
  - generated skill path: `<work_dir>/<sandbox_env_skill_path>` when configured as relative path
  - service/tool input mount paths (for example MCP host path) are **not** rewritten by `work_dir`
