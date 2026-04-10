# GDB CLI for AI

A GDB debugging tool designed specifically for AI Agents. It wraps GDB with an Agent-friendly interface through a streamlined CLI command set, outputting structured JSON.

## Features

- **Non-interactive**: All parameters passed via command line, no interactive prompts
- **Session-based**: Sessions persist across calls via session_id
- **Structured Output**: JSON format output, common commands auto-parsed
- **All-Stop Synchronous Blocking Mode**: `continue`, `run`, `step` etc. block until program stops

## Requirements

| Dependency | Version |
|------------|--------|
| GDB | 9.0+ |
| Python | 3.10+ |
| pexpect | 4.0+ |
| OS | Linux |

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd gdb-cli

# Install as a system tool
uv tool install .
```

After installation, you can run `gdb-cli` directly from anywhere:

```bash
gdb-cli start
# Output: {"session_id": "abc123", "status": "ready", "working_dir": "/path/to/cwd"}
```

Note: The first CLI call will auto-start the `gdb-cli-server` daemon if not running.

## Uninstallation

```bash
uv tool uninstall gdb-cli

# Remove session data (optional)
rm -rf ~/.gdb-cli/
```

## Commands

### start - Start Session

```bash
gdb-cli start

# Returns
{"session_id": "abc123", "status": "ready", "working_dir": "/path/to/cwd"}
```

Starts an empty GDB session. Use `command "file <path>"` to load a program.

### terminate - Terminate Session

```bash
gdb-cli terminate --session <id>

# Returns
{"session_id": "...", "status": "terminated"}
```

### command - Execute GDB Command

```bash
gdb-cli command --session <id> "bt" [--timeout 30]

# Structured parsed output (bt)
{"frames": [{"num": 0, "function": "main", "file": "main.c", "line": 10}], "truncated": false}

# Raw output (unknown command)
{"output": "..."}
```

Execute any GDB command. Common commands:
- `file <path>` - Load program
- `attach <pid>` - Attach to process
- `run` / `start` - Run program
- `break main` - Set breakpoint
- `bt` - View call stack
- `next` / `step` - Single step execution
- `print var` - Print variable
- `interrupt` - Interrupt running program

### status - Query Session Status

```bash
gdb-cli status --session <id>

# Returns
{"session_id": "...", "state": "alive", "target": "./my_app", "working_dir": "..."}
```

### sessions - List Sessions

```bash
gdb-cli sessions

# Returns
{"sessions": [...], "count": 3}
```

## Structured Parsed GDB Commands

| GDB Command | Parsed Fields |
|-------------|---------------|
| `bt` / `backtrace` | `frames[]` (num, function, file, line, address) |
| `info threads` | `threads[]` (id, target_id, current, frame, state) |
| `print` / `p` | `value`, `type`, `var` |
| `info registers` | `registers[]` (name, value) |
| `info breakpoints` | `breakpoints[]` (num, type, enabled, address, what) |
| `info sharedlibrary` | `libraries[]` (name, from, to) |
| `disassemble` | `instructions[]` (address, offset, asm) |
| Other commands | `output` (raw text) |

## Usage Examples

### Basic Debug Flow

```bash
# 1. Start session
gdb-cli start
# Output: {"session_id": "a1b2c3d4", "status": "ready", "working_dir": "..."}

# 2. Load program
gdb-cli command --session a1b2c3d4 "file ./my_app"

# 3. Set breakpoint
gdb-cli command --session a1b2c3d4 "break main"

# 4. Run program
gdb-cli command --session a1b2c3d4 "run" --timeout 30
# Output: {"output": "Breakpoint 1, main () at ..."}

# 5. View call stack
gdb-cli command --session a1b2c3d4 "bt"
# Output: {"frames": [{"num": 0, "function": "main", ...}], "truncated": false}

# 6. Single step
gdb-cli command --session a1b2c3d4 "next" --timeout 5

# 7. Print variable
gdb-cli command --session a1b2c3d4 "print argc"
# Output: {"var": "$1", "value": "1"}

# 8. Terminate session
gdb-cli terminate --session a1b2c3d4
```

### Attach to Running Process

```bash
gdb-cli start
# Output: {"session_id": "abc123", ...}

gdb-cli command --session abc123 "attach 12345"
gdb-cli command --session abc123 "bt"
gdb-cli terminate --session abc123
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     AI Agent                             │
└─────────────────────────┬───────────────────────────────┘
                          │ CLI Commands
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    CLI Layer                             │
│  start / terminate / command / status / sessions        │
│                          │                               │
│                          ▼                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │              GDBClient (client.py)                 │ │
│  │  - Unix Domain Socket communication                │ │
│  │  - JSON-RPC protocol                               │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │ Unix Socket
                          ▼
┌─────────────────────────────────────────────────────────┐
│            GDB Server Daemon (server.py)                 │
│  - Session management (in-memory)                       │
│  - pexpect spawn for GDB process                        │
│  - Async command blocking via prompt detection          │
│  - Interrupt support via Ctrl+C                         │
└─────────────────────────┬───────────────────────────────┘
                          │ pexpect
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     GDB Process                          │
└─────────────────────────────────────────────────────────┘
```

### Key Design: pexpect Blocking

For async commands (run, continue, step), the server uses `expect_exact("(gdb)")` to block until GDB returns to the prompt. This naturally captures all output including breakpoint hit information.

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test
uv run pytest tests/test_e2e.py -v
```

## Agent Skill

This project includes an Agent Skill file to guide AI Agents in using gdb-cli:

```
skills/gdb-debugging/SKILL.md
```

### Usage

Copy the skill to your Agent's skills directory:
```bash
# Claude Code
cp skills/gdb-debugging/SKILL.md ~/.claude/skills/

# Or use within project
# Agent will auto-load skills/ from project directory
```

## License

MIT License