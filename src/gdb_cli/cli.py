"""GDB CLI for AI - CLI entry point."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import click

from .client import GDBClient, DEFAULT_BASE_DIR, DEFAULT_SOCKET_NAME
from .output_parser import parse_output


def output_json(data: dict) -> None:
    """Output JSON to stdout."""
    click.echo(json.dumps(data, indent=2))


def get_client(socket_path: Optional[str] = None) -> GDBClient:
    """Get client instance."""
    if socket_path:
        return GDBClient(socket_path=Path(socket_path))
    return GDBClient()


def ensure_server_running(socket_path: Optional[str] = None) -> bool:
    """Check if server is running, start it if not."""
    client = get_client(socket_path)
    try:
        result = client.ping()
        return result.get("ok", False)
    except (socket.error, ConnectionRefusedError, FileNotFoundError):
        # Server not running, start it
        base_dir = Path(socket_path).parent if socket_path else DEFAULT_BASE_DIR
        sock_path = Path(socket_path) if socket_path else base_dir / DEFAULT_SOCKET_NAME

        # Start server in background
        subprocess.Popen(
            ["gdb-cli-server", "--socket", str(sock_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for server to start
        for _ in range(20):
            time.sleep(0.2)
            try:
                result = client.ping()
                return result.get("ok", False)
            except:
                continue

        return False


@click.group()
@click.version_option()
def main():
    """GDB CLI for AI - A GDB debugging tool with structured JSON output."""
    pass


@main.command()
@click.option("--socket", default=None, help="Socket path for RPC server")
def start(socket: Optional[str]):
    """Start a new GDB session."""
    if not ensure_server_running(socket):
        output_json({"ok": False, "error": "Failed to start GDB RPC server"})
        sys.exit(1)

    client = get_client(socket)
    try:
        result = client.start_session()
        if result.get("ok"):
            data = result.get("data", {})
            output_json({
                "session_id": data["session_id"],
                "status": "ready",
                "working_dir": data.get("working_dir", ""),
            })
        else:
            output_json(result)
            sys.exit(1)
    except Exception as e:
        output_json({"ok": False, "error": str(e)})
        sys.exit(1)


@main.command()
@click.option("--session", required=True, help="Session ID")
@click.option("--socket", default=None, help="Socket path for RPC server")
def terminate(session: str, socket: Optional[str]):
    """Terminate a GDB session."""
    client = get_client(socket)

    try:
        result = client.terminate_session(session)
        if result.get("ok"):
            output_json({
                "session_id": session,
                "status": "terminated",
            })
        else:
            output_json(result)
            sys.exit(1)
    except Exception as e:
        output_json({"ok": False, "error": str(e)})
        sys.exit(1)


@main.command("command")
@click.option("--session", required=True, help="Session ID")
@click.argument("gdb_command")
@click.option("--timeout", default=None, type=int, help="Command timeout in seconds")
@click.option("--max-length", default=None, type=int, help="Max output length (default 10000, truncated if exceeded)")
@click.option("--socket", default=None, help="Socket path for RPC server")
def exec_command(session: str, gdb_command: str, timeout: Optional[int], max_length: Optional[int], socket: Optional[str]):
    """Execute a GDB command."""
    client = get_client(socket)

    try:
        # Handle interrupt specially
        if gdb_command.strip().lower() == "interrupt":
            result = client.interrupt(session, timeout=timeout or 5)
        else:
            result = client.execute(session, gdb_command, timeout=timeout, max_length=max_length)

        if result.get("ok"):
            output_data = result.get("data", {})
            raw_output = output_data.get("output", "")
            truncated = output_data.get("truncated", False)
            total_bytes = output_data.get("total_bytes")

            # Try to parse output
            parsed = parse_output(gdb_command, raw_output)

            # Add truncation info if present
            if truncated:
                parsed["truncated"] = True
                parsed["total_bytes"] = total_bytes
                parsed["hint"] = "Output truncated. Use --max-length to increase limit or print specific fields."

            output_json(parsed)
        else:
            output_json(result)
    except TimeoutError as e:
        output_json({
            "ok": False,
            "error": str(e),
            "hint": "Use 'command --session <id> \"interrupt\"' to stop a running program",
        })
    except Exception as e:
        output_json({"ok": False, "error": str(e)})


@main.command()
@click.option("--session", required=True, help="Session ID")
@click.option("--socket", default=None, help="Socket path for RPC server")
def status(session: str, socket: Optional[str]):
    """Query session status."""
    client = get_client(socket)

    try:
        result = client.get_state(session)
        if result.get("ok"):
            data = result.get("data", {})
            output_json({
                "session_id": session,
                "state": "alive" if data.get("alive") else "terminated",
                "target": data.get("target", ""),
                "working_dir": data.get("working_dir", ""),
            })
        else:
            output_json(result)
    except Exception as e:
        output_json({"ok": False, "error": str(e)})


@main.command()
@click.option("--socket", default=None, help="Socket path for RPC server")
def sessions(socket: Optional[str]):
    """List active sessions."""
    client = get_client(socket)

    try:
        result = client.list_sessions()
        if result.get("ok"):
            data = result.get("data", {})
            output_json({
                "sessions": data.get("sessions", []),
                "count": data.get("count", 0),
            })
        else:
            output_json(result)
    except Exception as e:
        output_json({"ok": False, "error": str(e)})


if __name__ == "__main__":
    main()