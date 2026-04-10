---
name: gdb-debugging
description: Debug C/C++ programs with GDB using a structured, agent-friendly CLI interface. Provides session management, breakpoint control, variable inspection, and crash analysis.
---

# GDB Debugging Skill

Debug C/C++ programs with GDB through a structured CLI that returns JSON output. Manage sessions, set breakpoints, step through code, and analyze crashes.

## When to Use

TRIGGER when:
- User asks to debug a C/C++ program
- User mentions GDB, breakpoints, backtrace, stepping through code
- User wants to inspect variables, registers, or memory
- User needs to attach to a running process
- User encounters a crash or segmentation fault
- User has a coredump file to analyze

## Prerequisites

```bash
which gdb-cli || echo "Install gdb-cli first"
```

Ensure:
- GDB 9.0+
- Target binary compiled with debug symbols (`-g`)
- For attach: proper ptrace permissions

---

## Three Typical Scenarios (SOP)

### Scenario 1: Debug a Program from Start

**When to use**: Debug a program from the beginning, set breakpoints, step through code.

**Prerequisites**: Binary compiled with `-g`, source files accessible.

```bash
# Step 1: Create session
gdb-cli start
# Output: {"session_id": "abc123", "status": "ready", ...}
# SAVE session_id for all subsequent commands

# Step 2: Load the binary
gdb-cli command --session abc123 "file ./my_program"

# Step 3: Set breakpoints (optional but recommended)
gdb-cli command --session abc123 "break main"
gdb-cli command --session abc123 "break critical_function"

# Step 4: Run the program
gdb-cli command --session abc123 "run"
# OR use "start" to stop at main automatically:
# gdb-cli command --session abc123 "start"

# Step 5: Debug (after breakpoint hit)
gdb-cli command --session abc123 "bt"           # View call stack
gdb-cli command --session abc123 "info locals" # View local variables
gdb-cli command --session abc123 "next"        # Step over
gdb-cli command --session abc123 "continue"    # Continue

# Step 6: Cleanup
gdb-cli terminate --session abc123
```

**With command-line arguments**:
```bash
gdb-cli command --session abc123 "set args --config config.json --verbose"
gdb-cli command --session abc123 "run"
```

---

### Scenario 2: Analyze Coredump (Post-Mortem Debugging)

**When to use**: Program crashed and generated a coredump. Analyze the crash without re-running.

**Prerequisites**: 
- Binary compiled with `-g`
- Coredump file available
- Binary matches the one that crashed

```bash
# Step 1: Create session
gdb-cli start
# Output: {"session_id": "abc123", ...}

# Step 2: Load the binary
gdb-cli command --session abc123 "file ./my_program"

# Step 3: Load coredump
gdb-cli command --session abc123 "core-file /path/to/core.12345"
# OR with both in one command:
# gdb-cli command --session abc123 "core-file /path/to/core.12345 ./my_program"

# Step 4: Analyze the crash
gdb-cli command --session abc123 "bt"              # Where did it crash?
gdb-cli command --session abc123 "bt full"         # Full backtrace with locals
gdb-cli command --session abc123 "info registers"  # Register state at crash
gdb-cli command --session abc123 "frame 0"         # Switch to crashed frame
gdb-cli command --session abc123 "info locals"     # Local variables in that frame
gdb-cli command --session abc123 "print *ptr"      # Inspect pointer value

# Step 5: Cleanup
gdb-cli terminate --session abc123
```

**Common crash analysis commands**:
```bash
gdb-cli command --session abc123 "print errno"           # Check errno
gdb-cli command --session abc123 "x/10x $rsp"            # Examine stack memory
gdb-cli command --session abc123 "info threads"          # Check all threads
gdb-cli command --session abc123 "thread apply all bt"   # Backtrace all threads
```

---

### Scenario 3: Attach to Running Process

**When to use**: Debug a process that's already running (production issue, hung process, etc.)

**Prerequisites**:
- Process is running (find PID with `ps aux | grep my_program`)
- ptrace permissions (check `/proc/sys/kernel/yama/ptrace_scope`)

```bash
# Step 1: Find the process PID
ps aux | grep my_program
# Or: pgrep -f my_program

# Step 2: Create session
gdb-cli start
# Output: {"session_id": "abc123", ...}

# Step 3: Attach to the process
gdb-cli command --session abc123 "attach 12345"
# This stops the process

# Step 4: Inspect the running state
gdb-cli command --session abc123 "bt"              # Where is it stuck?
gdb-cli command --session abc123 "info threads"    # All threads
gdb-cli command --session abc123 "thread 2"        # Switch thread
gdb-cli command --session abc123 "bt"              # That thread's backtrace

# Step 5: Continue or control execution
gdb-cli command --session abc123 "continue"    # Let it run
# OR set breakpoints first:
gdb-cli command --session abc123 "break some_function"
gdb-cli command --session abc123 "continue"

# Step 6: Detach (let process continue without GDB)
gdb-cli command --session abc123 "detach"

# Step 7: Cleanup
gdb-cli terminate --session abc123
```

**If process is hung/stuck**:
```bash
# After attach, check where each thread is:
gdb-cli command --session abc123 "thread apply all bt"

# Look for:
# - Threads waiting on locks/mutexes
# - Threads blocked on I/O
# - Infinite loops
```

---

## CLI Commands Reference

| Command | Purpose |
|---------|---------|
| `gdb-cli start` | Create a new GDB session |
| `gdb-cli terminate --session <id>` | Destroy a session |
| `gdb-cli command --session <id> "<cmd>"` | Execute any GDB command |
| `gdb-cli status --session <id>` | Query session status |
| `gdb-cli sessions` | List all active sessions |

**Save the session_id from start** - all subsequent commands require it.

## Common GDB Commands

### Program Control

| GDB Command | Description |
|-------------|-------------|
| `file ./my_app` | Load program |
| `attach <pid>` | Attach to running process |
| `run [args]` | Start program with optional arguments |
| `start` | Start and stop at main |
| `continue` | Continue execution |
| `next` | Step over |
| `step` | Step into |
| `finish` | Step out of current function |
| `interrupt` | Interrupt running program |

### Breakpoints

| GDB Command | Description |
|-------------|-------------|
| `break main` | Break at function |
| `break file.c:50` | Break at line |
| `break func if x > 10` | Conditional breakpoint |
| `info breakpoints` | List breakpoints |
| `delete 1` | Delete breakpoint #1 |
| `disable 1` | Disable breakpoint #1 |
| `enable 1` | Enable breakpoint #1 |

### Inspection

| GDB Command | Description |
|-------------|-------------|
| `bt` | Backtrace |
| `bt full` | Backtrace with local variables |
| `frame N` | Switch to frame N |
| `info locals` | Local variables |
| `info args` | Function arguments |
| `print var` | Print variable |
| `print *ptr` | Dereference pointer |
| `info registers` | CPU registers |
| `info threads` | List threads |
| `thread N` | Switch to thread N |

### Coredump-Specific

| GDB Command | Description |
|-------------|-------------|
| `core-file /path/to/core` | Load coredump |
| `info signals` | Show signal that caused crash |
| `info proc mappings` | Memory mappings |

## Runtime Commands Block

Commands like `run`, `start`, `continue`, `step`, `next` block until:
- Program hits a breakpoint
- Program exits
- Timeout is reached (default: 30s)
- User interrupts with `interrupt`

Only use `--timeout` when you expect the program to run longer than 30 seconds (e.g., long-running tests, slow startup).

## Structured Output

These commands return parsed JSON:

| Command | Parsed Fields |
|---------|---------------|
| `bt` | `frames[]` with num, function, file, line, address |
| `info threads` | `threads[]` with id, state, current flag |
| `print VAR` | `var`, `value`, `type` |
| `info registers` | `registers[]` with name, value |
| `info breakpoints` | `breakpoints[]` with num, type, enabled |

### Backtrace Output Example

```json
{
  "frames": [
    {"num": 0, "function": "process_data", "file": "processor.c", "line": 42},
    {"num": 1, "function": "main", "file": "main.c", "line": 15}
  ],
  "truncated": false
}
```

## Error Handling

```json
{"ok": false, "error": "Session not found: abc123"}
{"ok": false, "error": "Command timed out", "hint": "Use 'interrupt' to stop"}
```

On timeout, use `gdb-cli command --session <id> "interrupt"` to stop the program.

## Navigation

- **[📋 Command Reference](./references/commands.md)** - Complete GDB command reference

## Checklist Before Using

- [ ] `gdb-cli` available in PATH
- [ ] Target binary compiled with `-g`
- [ ] GDB 9.0+
- [ ] For attach: ptrace permissions enabled (`echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope`)
- [ ] For coredump: ulimit set (`ulimit -c unlimited`)