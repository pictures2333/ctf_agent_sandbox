# ctf_agent_sandbox Current Design

本文件描述目前版本的實際設計與行為，供開發與除錯時快速對照。

## 1. 核心目標

此工具負責：

- 依照 `config` 組裝 Docker 執行環境
- 輸出組裝產物（Dockerfile、startup script、state file、env skill）
- 使用 Docker SDK 執行 `build image` / `run container` / `stop container`

## 2. API 設計

- `assemble(config, work_dir=...) -> AssemblyResult`
  - 只回傳記憶體結果，不寫檔。
- `assemble_and_write(config, work_dir=...) -> AssemblyResult`
  - 寫出組裝產物到 `work_dir`（與相關輸出路徑）。
- `build_image(config, tag=None, verbose=False, work_dir=...) -> image_id`
  - build image，並寫 state。
- `run_container(work_dir=...) -> container_id`
  - 讀取 state 後啟動容器。
- `stop_container(container_id) -> None`
  - 停止並刪除容器。

## 3. CLI 設計

- `assemble --config <path> --work-dir <dir>`
- `assemble-and-write --config <path> --work-dir <dir>`
- `build-image --config <path> --work-dir <dir> [--tag ...] [--verbose]`
- `run-container --work-dir <dir>`
- `stop-container --container-id <id>`

## 4. work_dir 的作用範圍

`work_dir` 只用於「本工具輸出」整理，不會改寫 service/tool 的外部輸入掛載路徑。

### 4.1 受 work_dir 影響（輸出）

- `<work_dir>/Dockerfile`
- `<work_dir>/script/startup.sh`
- `<work_dir>/.state.json`
- 由 `startup_script_host_path` 指定的輸出（若相對路徑，會落在 `work_dir` 下）
- 由 `sandbox_env_skill_path` 指定的輸出（若相對路徑，會落在 `work_dir` 下）

### 4.2 不受 work_dir 改寫（輸入）

- service options 內的 host 路徑（例如 MCP `host_path`）
- agent CLI tool options 內的 auth/config host 路徑
- 其他使用者明確指定的輸入來源路徑（除非其本身就是輸出欄位）

## 5. State File 規格

state 檔固定只有兩個欄位：

- `image_id`
- `run_params`

預設檔名：`.state.json`（位於 `work_dir` 底下）。

## 6. 為什麼會有兩份 startup.sh

`assemble-and-write` / `build_image` 目前會同時處理兩種用途：

1. 組裝產物檔：
- `<work_dir>/script/startup.sh`

2. runtime bind mount 目標檔：
- `startup_script_host_path`（預設相對路徑為 `.sandbox_generated/script/startup.sh`，因此在 `work_dir` 下會看到第二份）

這是刻意分開「產物輸出」與「容器掛載來源」兩種需求。

## 7. 預設路徑

- 預設 `work_dir`：`./.sandbox_workdir`
- 預設 config 檔名：`config.yaml`（由 CLI `--config` 指定時可覆蓋）
- 預設 state 檔名：`.state.json`

