"""GDB output parser.

Parses GDB output into structured JSON format for common commands.
"""

import re
from typing import Any


def parse_backtrace(output: str) -> dict:
    """Parse GDB backtrace output.

    Args:
        output: Raw GDB backtrace output

    Returns:
        {"frames": [{"num", "function", "file", "line", "address"}]}
    """
    frames = []

    # Pattern: #NUM [ADDRESS in] FUNCTION [(ARGS)] [at FILE:LINE]
    pattern = r"#(\d+)\s+(?:0x([0-9a-fA-F]+)\s+in\s+)?(\w+)\s*(?:\([^)]*\))?\s*(?:at\s+(\S+):(\d+))?"

    for match in re.finditer(pattern, output):
        frame = {
            "num": int(match.group(1)),
            "function": match.group(3),
        }
        if match.group(2):
            frame["address"] = f"0x{match.group(2)}"
        if match.group(4):
            frame["file"] = match.group(4)
        if match.group(5):
            frame["line"] = int(match.group(5))
        frames.append(frame)

    return {"frames": frames, "truncated": False}


def parse_threads(output: str) -> dict:
    """Parse GDB info threads output.

    Args:
        output: Raw GDB info threads output

    Returns:
        {"threads": [{"id", "target_id", "frame", "current", "state"}]}
    """
    threads = []

    # Pattern: [*] ID Target Id "NAME" [Frame]
    lines = output.strip().split("\n")
    for line in lines:
        # Skip header
        if "Id" in line and "Target Id" in line:
            continue
        if not line.strip():
            continue

        # Check if current thread (marked with *)
        current = line.startswith("*")
        line = line.lstrip("*").strip()

        # Parse thread id and rest
        match = re.match(r"(\d+)\s+(.+)", line)
        if match:
            thread_id = int(match.group(1))
            rest = match.group(2).strip()

            # Parse target_id - everything up to frame or (running)
            # Target id is typically: process PID "NAME"
            target_match = re.match(r'(process\s+\d+\s+"[^"]+")', rest)
            if target_match:
                target_id = target_match.group(1)
                remaining = rest[len(target_id):].strip()
            else:
                # Fallback: split by first space
                parts = rest.split(None, 1)
                target_id = parts[0] if parts else ""
                remaining = parts[1] if len(parts) > 1 else ""

            thread = {
                "id": thread_id,
                "target_id": target_id,
                "current": current,
            }

            # Check for state like "(running)" or frame info
            if remaining.startswith("(") and remaining.endswith(")"):
                thread["state"] = remaining[1:-1]
            elif remaining:
                thread["frame"] = remaining

            threads.append(thread)

    return {"threads": threads}


def parse_print(output: str) -> dict:
    """Parse GDB print output.

    Args:
        output: Raw GDB print output

    Returns:
        {"var", "value", "type"}
    """
    result = {}

    # Pattern: $VAR = [TYPE] VALUE
    # Handle: $1 = 42
    # Handle: $2 = (int *) 0x555555555abc
    match = re.match(r"\$(\d+)\s+=\s+(?:\(([^)]+)\)\s+)?(.+)", output.strip())
    if match:
        result["var"] = "$" + match.group(1)
        if match.group(2):
            result["type"] = match.group(2)
        result["value"] = match.group(3).strip()

    return result


def parse_registers(output: str) -> dict:
    """Parse GDB info registers output.

    Args:
        output: Raw GDB info registers output

    Returns:
        {"registers": [{"name", "value", "raw_value"}]}
    """
    registers = []

    for line in output.strip().split("\n"):
        # Pattern: NAME VALUE [RAW_VALUE]
        match = re.match(r"(\w+)\s+(0x[0-9a-fA-F]+)\s*(\S+)?", line)
        if match:
            reg = {
                "name": match.group(1),
                "value": match.group(2),
            }
            if match.group(3):
                reg["raw_value"] = match.group(3)
            registers.append(reg)

    return {"registers": registers}


def parse_breakpoints(output: str) -> dict:
    """Parse GDB info breakpoints output.

    Args:
        output: Raw GDB info breakpoints output

    Returns:
        {"breakpoints": [{"num", "type", "enabled", "address", "what"}]}
    """
    breakpoints = []

    lines = output.strip().split("\n")
    for i, line in enumerate(lines):
        # Skip header
        if "Num" in line and "Type" in line:
            continue
        if not line.strip():
            continue
        # Skip continuation lines
        if line.startswith("\t") or line.startswith(" "):
            continue

        # Pattern: NUM TYPE DISP ENB ADDRESS WHAT
        match = re.match(
            r"(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(0x[0-9a-fA-F]+)\s+(.+)",
            line.strip()
        )
        if match:
            bp = {
                "num": int(match.group(1)),
                "type": match.group(2),
                "disp": match.group(3),
                "enabled": match.group(4) == "y",
                "address": match.group(5),
                "what": match.group(6).strip(),
            }
            breakpoints.append(bp)

    return {"breakpoints": breakpoints}


def parse_sharedlibrary(output: str) -> dict:
    """Parse GDB info sharedlibrary output.

    Args:
        output: Raw GDB info sharedlibrary output

    Returns:
        {"libraries": [{"name", "from", "to", "syms_read"}]}
    """
    libraries = []

    # Handle empty case
    if "No shared libraries loaded" in output:
        return {"libraries": []}

    for line in output.strip().split("\n"):
        # Skip header
        if "From" in line and "To" in line:
            continue
        if not line.strip():
            continue

        # Pattern: FROM TO SYMS_READ NAME
        match = re.match(
            r"(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(\S+)\s+(.+)",
            line.strip()
        )
        if match:
            lib = {
                "from": match.group(1),
                "to": match.group(2),
                "syms_read": match.group(3),
                "name": match.group(4).strip(),
            }
            libraries.append(lib)

    return {"libraries": libraries}


def parse_disassemble(output: str) -> dict:
    """Parse GDB disassemble output.

    Args:
        output: Raw GDB disassemble output

    Returns:
        {"instructions": [{"address", "offset", "asm"}]}
    """
    instructions = []

    for line in output.strip().split("\n"):
        # Pattern: ADDRESS <FUNCTION+OFFSET>: ASM
        match = re.match(
            r"\s*(0x[0-9a-fA-F]+)\s+<([^>]+)>:\s+(.+)",
            line.strip()
        )
        if match:
            inst = {
                "address": match.group(1),
                "offset": match.group(2),
                "asm": match.group(3).strip(),
            }
            instructions.append(inst)

    return {"instructions": instructions}


def parse_output(command: str, output: str) -> dict:
    """Auto-detect command type and parse output.

    Args:
        command: The GDB command that was executed
        output: Raw GDB output

    Returns:
        Structured output or raw output if unknown command
    """
    # Normalize command
    cmd = command.strip().lower()

    # Detect command type and parse
    if cmd in ("bt", "backtrace", "where"):
        return parse_backtrace(output)
    elif cmd == "info threads":
        return parse_threads(output)
    elif cmd.startswith(("p ", "print ", "x/")):
        return parse_print(output)
    elif cmd == "info registers" or cmd.startswith("info registers "):
        return parse_registers(output)
    elif cmd == "info breakpoints" or cmd.startswith("info breakpoints "):
        return parse_breakpoints(output)
    elif cmd == "info sharedlibrary":
        return parse_sharedlibrary(output)
    elif cmd == "disassemble" or cmd.startswith("disassemble "):
        return parse_disassemble(output)
    else:
        # Unknown command - return raw output
        return {"output": output}