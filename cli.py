"""CLI entrypoint for sandbox assembly and Docker runtime operations."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .assembler import STATE_FILE, assemble_and_write, build_image, run_container, stop_container
from .models import SandboxConfig


def _load_config(path: str) -> SandboxConfig:
    """Load and validate sandbox config from YAML file path."""
    config_path = Path(path)
    if not config_path.exists():
        raise SystemExit(f"{config_path} not found (CLI expects a YAML object file)")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise SystemExit(f"{config_path} must contain a YAML object at top level")
    return SandboxConfig.model_validate(raw)


def _build_parser() -> argparse.ArgumentParser:
    """Build modern subcommand CLI parser aligned with package API."""
    parser = argparse.ArgumentParser(description="CTF sandbox assembler CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    assemble_parser = subparsers.add_parser("assemble", help="Generate Dockerfile/startup/state template")
    assemble_parser.add_argument("--config", default="config.yaml", help="Path to YAML config object")
    assemble_parser.add_argument("--output-dir", default=".", help="Where to write generated files")
    assemble_parser.add_argument(
        "--state-file",
        default=str(STATE_FILE),
        help="Path to write state file template (image_id + run_params)",
    )

    build_parser = subparsers.add_parser("build-image", help="Build image and persist package state file")
    build_parser.add_argument("--config", default="config.yaml", help="Path to YAML config object")
    build_parser.add_argument("--tag", default=None, help="Optional docker image tag override")

    run_parser = subparsers.add_parser("run-container", help="Run container and print container id")
    run_parser.add_argument(
        "--state-file",
        default=str(STATE_FILE),
        help="Path to state file for image id and run params",
    )

    stop_parser = subparsers.add_parser("stop-container", help="Stop and remove container by id")
    stop_parser.add_argument("--container-id", required=True, help="Container id to stop/remove")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args and dispatch to API-equivalent operations."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "assemble":
        config = _load_config(args.config)
        assemble_and_write(config, output_dir=args.output_dir, state_file=args.state_file)
        return 0

    if args.command == "build-image":
        config = _load_config(args.config)
        image_id = build_image(config=config, tag=args.tag)
        print(image_id)
        return 0

    if args.command == "run-container":
        container_id = run_container(state_file=args.state_file)
        print(container_id)
        return 0

    if args.command == "stop-container":
        stop_container(args.container_id)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
