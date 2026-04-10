"""GDB RPC Client.

Communicates with GDB RPC server via Unix Domain Socket.
"""

import json
import socket
import time
from pathlib import Path
from typing import Any, Optional


DEFAULT_BASE_DIR = Path.home() / ".gdb-cli"
DEFAULT_SOCKET_NAME = "gdb-cli.sock"


class GDBClient:
    """Client for communicating with GDB RPC server."""

    DEFAULT_TIMEOUT = 30
    CONNECT_TIMEOUT = 5

    def __init__(self, socket_path: Optional[Path] = None, timeout: Optional[float] = None):
        """Initialize client.

        Args:
            socket_path: Path to Unix Domain Socket
            timeout: Default request timeout in seconds
        """
        self.socket_path = socket_path or (DEFAULT_BASE_DIR / DEFAULT_SOCKET_NAME)
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    def _connect(self) -> socket.socket:
        """Connect to the RPC server."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.CONNECT_TIMEOUT)
        sock.connect(str(self.socket_path))
        return sock

    def _send_request(self, request: dict, timeout: Optional[float] = None) -> dict:
        """Send a request and get response."""
        sock = self._connect()
        timeout = timeout or self.timeout
        sock.settimeout(timeout)

        try:
            sock.sendall(json.dumps(request).encode())
            sock.shutdown(socket.SHUT_WR)

            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

            if not data:
                raise RuntimeError("Empty response from server")

            return json.loads(data.decode())

        except socket.timeout:
            raise TimeoutError(f"Request timed out after {timeout}s")
        finally:
            sock.close()

    def ping(self) -> dict:
        """Ping the server."""
        return self._send_request({"cmd": "ping"}, timeout=5)

    def start_session(
        self,
        gdb_path: str = "gdb",
        working_dir: Optional[str] = None,
        startup_timeout: float = 10.0,
    ) -> dict:
        """Start a new GDB session."""
        return self._send_request({
            "cmd": "start_session",
            "gdb_path": gdb_path,
            "working_dir": working_dir,
            "startup_timeout": startup_timeout,
        })

    def execute(self, session_id: str, command: str, timeout: Optional[float] = None) -> dict:
        """Execute a GDB command."""
        return self._send_request({
            "cmd": "execute",
            "session_id": session_id,
            "command": command,
            "timeout": timeout or self.timeout,
        }, timeout=timeout or self.timeout)

    def interrupt(self, session_id: str, timeout: float = 5.0) -> dict:
        """Interrupt a running program."""
        return self._send_request({
            "cmd": "interrupt",
            "session_id": session_id,
            "timeout": timeout,
        }, timeout=timeout)

    def get_state(self, session_id: str) -> dict:
        """Get session state."""
        return self._send_request({
            "cmd": "get_state",
            "session_id": session_id,
        })

    def terminate_session(self, session_id: str) -> dict:
        """Terminate a session."""
        return self._send_request({
            "cmd": "terminate_session",
            "session_id": session_id,
        })

    def list_sessions(self) -> dict:
        """List active sessions."""
        return self._send_request({"cmd": "list_sessions"})


def get_client(socket_path: Optional[Path] = None) -> GDBClient:
    """Get a client instance."""
    return GDBClient(socket_path=socket_path)