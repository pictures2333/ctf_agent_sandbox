# Runtime I/O Contract

This note defines the required input/output contract for sandbox runtime APIs and CLI commands.
The same contract must be kept aligned across `assembler.py`, `cli.py`, tests, and `README.md`.

## State File Rule

- State file content must contain only:
  - `image_id`
  - `run_params`
- No other top-level fields are allowed.

## API Contract

### `assemble(config, work_dir="./.sandbox_workdir") -> AssemblyResult`

- Inputs:
  - `config`: sandbox config object/dict
  - `work_dir`: output root directory for generated artifacts
- Outputs:
  - return value: `AssemblyResult`
    - `dockerfile`
    - `startup_script`
    - `container_options`
- Side effects:
  - none (in-memory only)

### `assemble_and_write(config, work_dir="./.sandbox_workdir") -> AssemblyResult`

- Inputs:
  - `config`: sandbox config object/dict
  - `work_dir`: generated Dockerfile/startup/state output directory
- Outputs:
  - return value: `AssemblyResult`
  - side effects:
    - write `<work_dir>/Dockerfile`
    - write `<work_dir>/script/startup.sh`
    - write `<work_dir>/.state.json` with `{image_id: null, run_params}`

### `build_image(config, tag=None, verbose=False, work_dir="./.sandbox_workdir") -> str`

- Inputs:
  - `config`: sandbox config object/dict
  - `tag`: optional image tag override
  - `verbose`: whether to stream build logs
  - `work_dir`: state/output root directory
- Outputs:
  - return value: `image_id`
  - side effect: write `<work_dir>/.state.json` with `{image_id, run_params}`

### `run_container(work_dir="./.sandbox_workdir") -> str`

- Inputs:
  - `work_dir`: directory containing previously generated `.state.json`
- Outputs:
  - return value: `container_id`
  - side effect: run one container

### `stop_container(container_id: str) -> None`

- Inputs:
  - `container_id`
- Outputs:
  - no return value
  - side effect: stop and remove container

## CLI Contract

### `assemble`

- Must expose and pass through:
  - `--config`
  - `--work-dir`
- Behavior:
  - load config from `--config`
  - call API `assemble`
  - print JSON result only
  - no file output

### `assemble-and-write`

- Must expose and pass through:
  - `--config`
  - `--work-dir`
- Behavior:
  - load config from `--config`
  - call API `assemble_and_write`
  - write Dockerfile/startup/state artifacts

### `build-image`

- Must expose and pass through:
  - `--config`
  - `--work-dir`
  - `--tag`
  - `--verbose`

### `run-container`

- Must expose and pass through:
  - `--work-dir`

### `stop-container`

- Must expose and pass through:
  - `--container-id`

## Alignment Rule

- If API input/output changes, CLI and README must be updated in the same change.
- If CLI option changes, API call wiring and tests must be updated in the same change.

## Work Directory Scope

- `work_dir` only controls this tool's generated outputs:
  - Dockerfile
  - startup script
  - state file
  - generated sandbox env skill
- `work_dir` must not rewrite unrelated input mount paths (for example MCP service host paths).
