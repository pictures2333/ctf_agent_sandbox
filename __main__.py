"""Module entrypoint for `uv run -m ctf_agent_sandbox`."""

from .cli import main

# Delegate module execution to the CLI entrypoint.
raise SystemExit(main())
