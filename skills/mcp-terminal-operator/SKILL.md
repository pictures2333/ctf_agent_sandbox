---
name: mcp-terminal-operator
description: Use this skill when interacting with the MCP Terminal server. Apply it whenever AI agent must run shell commands through a persistent terminal session, inspect terminal output, handle long output with offset-based paging, send control signals such as enter or interrupt, and close sessions safely.
---

# MCP Terminal Operator

Use the MCP terminal as a persistent shell, not as a stateless command runner.

## Workflow

Follow this workflow strictly. Do not skip steps unless the current session has already completed the earlier required step.

### 1. Open a session

- Open a session with `session_open`.
- Save the returned `session_id`.

### 2. Interact with your session

- Send text with `session_input`.
- If a command should execute immediately, send `signal="enter"`.
- Read terminal output with `session_output`.
- Continue polling `session_output` when the command is interactive or may produce delayed output.
- Continue the steps above if:
    - Want to execute another command.
    - Want to interact with the command (or executable) like ``gdb``

### 3. Close session

Close the session with `session_close` when the task is finished.

To save resources, do not forget to close the session when your task is finished.

## Operating Rules

- Reuse the same `session_id` for related commands in the same task.
- Treat the session as stateful. The current working directory, shell variables, and previous commands may affect later commands.
- After every meaningful `session_input`, call `session_output` to inspect the actual result.
- Do not assume a command succeeded only because `session_input` returned `accepted=true`.
- If the shell may still be running a foreground process, keep checking `session_output` before sending more commands.
- If a process appears stuck or is taking too long, send `session_input(signal="interrupt")`.
- Always call `session_close` when the session is no longer needed.
- Do not read too many outputs once.

## Input Patterns

Use `session_input(data="command", signal="enter")` for a normal shell command.

Use `session_input(data="partial text")` when building up input without submitting it yet.

Use these signals intentionally:
- `enter`: submit the current line
- `interrupt`: send Ctrl-C to stop the foreground process
- `eof`: send Ctrl-D to end input

## Output Reading Strategy

Use `session_output(session_id, limit, offset)` to inspect the tail of the output buffer.

Interpret the response this way:

- `data`: terminal text returned for this window
- `bytes`: size of `data` in bytes
- `buffer_size`: total bytes currently retained in the buffer
- `has_more_before=true`: older output exists before this window
- `has_more_before=false`: this window already reaches the oldest retained output

When output may be long:

1. Start with `offset=0`.
2. If the returned text is incomplete and `has_more_before=true`, request older output by increasing `offset`.
3. Continue until `has_more_before=false` or the needed context has been recovered.

Use larger `limit` values only when needed. Prefer smaller reads first to avoid filling model context with unnecessary terminal text.

## Decision Heuristics

- Open one session per task unless isolation is needed.
- Reuse a session for multi-step shell work such as `cd`, file inspection, editing, and follow-up commands.
- Open a fresh session when previous shell state may be confusing or risky.
- If output is empty right after input, poll again rather than assuming nothing happened.
- If the task is complete, close the session immediately instead of leaving it idle.


## Failure Handling

- If a tool reports `missing=true`, assume the session no longer exists and open a new one if needed.
- If `session_close` returns `already_closed=true`, treat cleanup as complete.
- If command results are unclear, inspect `session_output` again before retrying input.
- If older output is needed for reasoning, use `has_more_before` and `offset` rather than guessing what happened earlier.


## Examples

### Example 1: Interactive Tools

The example shows how to use an interactive tool like GDB via the MCP Terminal.

1. Use ``session_open()`` to open a new session.
2. Use ``session_input()`` to open GDB.
    ```
    data: gdb <target>
    signal: enter
    ```
3. Inspect output, GDB is running in the terminal.
4. You can use ``session_input()`` to enter some GDB commands. For example:
    ```
    data: b main
    signal: enter
    ```
5. Inspect output.

The example shows how to use GDB in the terminal. 

You can use any tools in the terminal, and interact with them.

### Example 2: Binary Exploitation Tips

You can use GDB in the terminal so that you can debug an executable or a process in an interactive way.

You can open many sessions.
- You can run GDB, the executable or other tools in the same time.
- You can run the exploit script, and open a GDB to attach the process.
    ```
    Session 1: Run your exploit script.
    Session 2: Open GDB. Attach to the process and you can debug your exploit.
    ```

(If you use pwntools) Use ``raw_input()`` as a breakpoint in your exploit script.
1. Run your exploit script.
2. Exploit script hit a ``raw_input()``.
3. And you have time to attach the process in GDB.
4. Back to exploit script and press ``enter``.
5. Now you can debug the process and exploit script.

> Pwners like to use ``pwndbg`` which is a gdb plugin for pwn. 
> 
> GDB with pwndbg will be "colorful".
>
> Agent can add ``TERM=dumb`` and execute gdb for cleaner outputs.
>
> ``TERM=dumb gdb <target>``