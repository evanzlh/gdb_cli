# GDB Command Reference

Complete reference for GDB CLI commands with examples.

## Session Management

### Start Session

```bash
# Start empty session, load binary later
gdb-cli start
# Returns: {"ok": true, "session_id": "abc123"}

# Start and load binary in one step
gdb-cli load --binary /path/to/program
# Returns: {"ok": true, "session_id": "abc123", "binary": "/path/to/program"}
```

### Attach to Process

```bash
# Attach by PID (creates session automatically)
gdb-cli attach --pid 12345

# Attach with existing session
gdb-cli start
gdb-cli attach --session abc123 --pid 12345
```

### List Sessions

```bash
gdb-cli sessions
# Returns: {"sessions": [{"session_id": "abc123", "binary": "./my_app", "status": "stopped"}]}
```

### Terminate Session

```bash
gdb-cli terminate --session abc123
# Returns: {"ok": true}
```

## Execution Commands

### Run Program

```bash
gdb-cli command --session $ID "run" --timeout 30
gdb-cli command --session $ID "run arg1 arg2" --timeout 30  # With arguments
```

Blocks until program stops (breakpoint, exit, crash, or timeout).

### Continue Execution

```bash
gdb-cli command --session $ID "continue" --timeout 30
```

### Step Commands

| Command | Description |
|---------|-------------|
| `next` (n) | Step over function calls |
| `step` (s) | Step into function calls |
| `finish` | Run until current function returns |
| `until` | Run until line or address |

```bash
gdb-cli command --session $ID "next"
gdb-cli command --session $ID "step"
gdb-cli command --session $ID "finish"
gdb-cli command --session $ID "until 50"  # Until line 50
```

### Interrupt

```bash
gdb-cli interrupt --session abc123
```

Use when a running command times out or needs to be interrupted.

## Breakpoint Commands

### Set Breakpoints

```bash
# Function breakpoint
gdb-cli command --session $ID "break main"

# Line breakpoint
gdb-cli command --session $ID "break file.c:50"

# Conditional breakpoint
gdb-cli command --session $ID "break func if x > 10"
gdb-cli command --session $ID "break file.c:50 if count == 0"

# Watchpoint (break on variable change)
gdb-cli command --session $ID "watch variable_name"

# Hardware watchpoint
gdb-cli command --session $ID "rwatch variable_name"  # Read
gdb-cli command --session $ID "awatch variable_name"  # Read/Write
```

### Manage Breakpoints

```bash
# List breakpoints
gdb-cli command --session $ID "info breakpoints"

# Enable/disable
gdb-cli command --session $ID "disable 1"
gdb-cli command --session $ID "enable 1"

# Delete
gdb-cli command --session $ID "delete 1"        # Delete breakpoint 1
gdb-cli command --session $ID "delete"          # Delete all
```

## Inspection Commands

### Backtrace

```bash
gdb-cli command --session $ID "bt"
gdb-cli command --session $ID "bt full"  # Include local variables
gdb-cli command --session $ID "bt 5"     # Limit to 5 frames
```

### Variables

```bash
# Print variable
gdb-cli command --session $ID "print variable_name"
gdb-cli command --session $ID "print *ptr"  # Dereference pointer
gdb-cli command --session $ID "print arr[0]@10"  # Print 10 elements

# Print in different formats
gdb-cli command --session $ID "print/x var"  # Hex
gdb-cli command --session $ID "print/d var"  # Decimal
gdb-cli command --session $ID "print/c var"  # Character

# Local variables
gdb-cli command --session $ID "info locals"
gdb-cli command --session $ID "info args"   # Function arguments
```

### Memory

```bash
# Examine memory
gdb-cli command --session $ID "x/10x 0x7fffffffe000"  # 10 hex values
gdb-cli command --session $ID "x/10i $pc"             # 10 instructions

# Disassemble
gdb-cli command --session $ID "disassemble main"
gdb-cli command --session $ID "disassemble/s main"   # With source
```

### Threads

```bash
gdb-cli command --session $ID "info threads"
gdb-cli command --session $ID "thread 2"    # Switch to thread 2
gdb-cli command --session $ID "thread apply all bt"  # Backtrace all threads
```

### Registers

```bash
gdb-cli command --session $ID "info registers"
gdb-cli command --session $ID "info registers rax rbx"  # Specific registers
gdb-cli command --session $ID "print $pc"   # Program counter
gdb-cli command --session $ID "print $sp"   # Stack pointer
```

## Source Navigation

```bash
gdb-cli command --session $ID "list"        # List source around current line
gdb-cli command --session $ID "list main"   # List function
gdb-cli command --session $ID "list file.c:50"  # List specific location
gdb-cli command --session $ID "list -"      # List previous lines
```

## Signal Handling

```bash
# View signal handling
gdb-cli command --session $ID "info signals"

# Change signal handling
gdb-cli command --session $ID "handle SIGINT stop print"
gdb-cli command --session $ID "handle SIGPIPE nostop noprint"
```

## Core Dump Analysis

```bash
gdb-cli load --binary ./my_program
gdb-cli command --session $ID "core-file /path/to/core"
gdb-cli command --session $ID "bt"
gdb-cli command --session $ID "info registers"
```

## Running with Arguments

```bash
gdb-cli load --binary ./my_program

# Run with arguments
gdb-cli command --session $ID "run --config /etc/app.conf --verbose" --timeout 30

# Or set arguments separately
gdb-cli command --session $ID "set args --config /etc/app.conf --verbose"
gdb-cli command --session $ID "run" --timeout 30

# Check arguments
gdb-cli command --session $ID "show args"
```