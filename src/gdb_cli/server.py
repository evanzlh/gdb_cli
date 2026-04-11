"""GDB RPC Server Daemon.

A daemon process that manages GDB sessions using pexpect and exposes
an RPC interface via Unix Domain Socket.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import signal
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pexpect


# Default paths
DEFAULT_BASE_DIR = Path.home() / ".gdb-cli"
DEFAULT_SOCKET_NAME = "gdb-cli.sock"

# Default output limits
DEFAULT_MAX_OUTPUT_LENGTH = 10000

# Default idle timeout (60 minutes)
DEFAULT_IDLE_TIMEOUT = 3600

# Cleanup check interval
CLEANUP_INTERVAL = 60

# Strip ANSI escape sequences
_ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1B
    (?:
        \[[0-?]*[ -/]*[@-~]
        |\][^\x07\x1B]*(?:\x07|\x1B\\)
        |[@-Z\\-_]
    )
    """,
    re.VERBOSE,
)

# Bootstrap commands
_BOOTSTRAP_COMMANDS = (
    "set pagination off",
    "set confirm off",
)


def _strip_terminal_escapes(raw: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", raw)


def _normalize_output(raw: str) -> str:
    text = _strip_terminal_escapes(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


@dataclass
class GdbSession:
    """A GDB session managed by pexpect."""

    session_id: str
    child: pexpect.spawn
    working_dir: Path
    gdb_path: str = "gdb"
    target: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now()

    def idle_seconds(self) -> float:
        """Return seconds since last activity."""
        return (datetime.now() - self.last_activity_at).total_seconds()

    @classmethod
    def start(
        cls,
        session_id: str,
        working_dir: Path,
        gdb_path: str = "gdb",
        startup_timeout: float = 10.0,
    ) -> "GdbSession":
        env = dict(os.environ)
        env["TERM"] = "dumb"

        child = pexpect.spawn(
            gdb_path,
            args=["--quiet", "--nx"],
            cwd=str(working_dir),
            encoding="utf-8",
            echo=False,
            timeout=startup_timeout,
            env=env,
        )

        try:
            child.expect_exact("(gdb)", timeout=startup_timeout)
            for cmd in _BOOTSTRAP_COMMANDS:
                child.sendline(cmd)
                child.expect_exact("(gdb)", timeout=startup_timeout)
        except pexpect.TIMEOUT as exc:
            child.close(force=True)
            raise RuntimeError(f"GDB startup timed out after {startup_timeout}s") from exc
        except pexpect.EOF as exc:
            child.close(force=True)
            raise RuntimeError("GDB exited before initial prompt") from exc

        return cls(
            session_id=session_id,
            child=child,
            working_dir=working_dir,
            gdb_path=gdb_path,
        )

    def is_alive(self) -> bool:
        return self.child.isalive()

    def interrupt(self) -> str:
        """Send Ctrl+C to interrupt a running program.

        This is non-blocking - it sends the interrupt signal and returns
        immediately. The pending execute() call will receive the prompt.
        """
        if not self.child.isalive():
            raise RuntimeError(f"GDB session {self.session_id} is not alive")

        # Update activity timestamp
        self.update_activity()

        # Send Ctrl+C to GDB - this will interrupt the running program
        # The pending execute() will then receive the prompt
        self.child.sendcontrol('c')

        return "Interrupt signal sent"

    def execute(self, command: str, timeout: float = 90.0, max_length: Optional[int] = None) -> dict:
        """Execute a GDB command and block until prompt returns.

        This naturally handles async commands (run, continue) - when
        program stops at breakpoint, GDB prints info and shows prompt.

        Returns:
            dict with "output" and "truncated" (if output was truncated)
        """
        with self._lock:
            if not self.child.isalive():
                raise RuntimeError(f"GDB session {self.session_id} is not alive")

            # Update activity timestamp
            self.update_activity()

            self.child.sendline(command)

            try:
                self.child.expect_exact("(gdb)", timeout=timeout)
            except pexpect.TIMEOUT as exc:
                partial = _normalize_output(self.child.before or "")
                raise TimeoutError(
                    f"Command timed out after {timeout}s. Partial output:\n{partial}"
                ) from exc
            except pexpect.EOF as exc:
                partial = _normalize_output(self.child.before or "")
                raise RuntimeError(
                    f"GDB session terminated. Partial output:\n{partial}"
                ) from exc

            output = _normalize_output(self.child.before or "")
            # Remove command echo
            lines = output.splitlines()
            if lines and lines[0].strip() == command.strip():
                lines = lines[1:]
            output = "\n".join(lines).strip()

            # Truncate if needed
            actual_max_length = max_length or DEFAULT_MAX_OUTPUT_LENGTH
            if len(output) > actual_max_length:
                truncated_len = len(output)
                output = output[:actual_max_length] + f"\n... [TRUNCATED: {truncated_len} bytes total, showing {actual_max_length} bytes]"
                return {"output": output, "truncated": True, "total_bytes": truncated_len}

            return {"output": output, "truncated": False}

    def terminate(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self.child.isalive():
                return
            try:
                self.child.sendline("quit")
                idx = self.child.expect_exact(["(y or n)", pexpect.EOF], timeout=timeout)
                if idx == 0:
                    self.child.sendline("y")
                    self.child.expect(pexpect.EOF, timeout=timeout)
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass
            finally:
                self.child.close(force=True)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "working_dir": str(self.working_dir),
            "gdb_path": self.gdb_path,
            "target": self.target or "No program loaded",
            "alive": self.is_alive(),
            "idle_seconds": round(self.idle_seconds(), 1),
        }


class GDBServer:
    """RPC server that manages GDB sessions."""

    def __init__(self, socket_path: Path, idle_timeout: float = DEFAULT_IDLE_TIMEOUT):
        self.socket_path = socket_path
        self.sessions: dict[str, GdbSession] = {}
        self._lock = threading.RLock()
        self._running = True
        self.idle_timeout = idle_timeout
        self._last_cleanup_check = time.time()

        # Setup socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.sock.bind(str(self.socket_path))
        self.sock.listen(5)
        self.sock.settimeout(1.0)

        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self.terminate_all)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        print(f"Received signal {signum}, shutting down...")
        self._running = False
        self.terminate_all()

    def _cleanup_idle_sessions(self) -> int:
        """Terminate sessions that have been idle too long.

        Returns:
            Number of sessions terminated
        """
        terminated_count = 0
        sessions_to_terminate = []

        with self._lock:
            for session_id, session in list(self.sessions.items()):
                if session.idle_seconds() > self.idle_timeout:
                    sessions_to_terminate.append(session_id)

        # Terminate outside lock to avoid blocking
        for session_id in sessions_to_terminate:
            with self._lock:
                session = self.sessions.pop(session_id, None)
            if session:
                try:
                    session.terminate()
                    terminated_count += 1
                    print(f"Terminated idle session {session_id} (idle for {session.idle_seconds():.0f}s)")
                except Exception as e:
                    print(f"Error terminating idle session {session_id}: {e}")

        return terminated_count

    def shutdown(self) -> dict:
        """Gracefully shutdown the server.

        Returns:
            Summary of shutdown
        """
        self._running = False
        sessions_count = len(self.sessions)
        self.terminate_all()
        return {"terminated_sessions": sessions_count, "status": "shutdown_complete"}

    def _resolve_gdb_path(self, gdb_path: str) -> str:
        if os.path.sep in gdb_path:
            candidate = Path(gdb_path).expanduser().resolve()
            if not candidate.exists():
                raise FileNotFoundError(f"GDB not found: {candidate}")
            return str(candidate)
        from shutil import which
        resolved = which(gdb_path)
        if resolved is None:
            raise FileNotFoundError(f"GDB not found in PATH: {gdb_path}")
        return resolved

    def _get_session(self, session_id: str) -> GdbSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"No active session: {session_id}")
        return session

    def handle_request(self, request: dict) -> dict:
        """Handle a JSON RPC request."""
        cmd = request.get("cmd", "")

        try:
            if cmd == "ping":
                return {"ok": True, "data": {"message": "pong"}}

            elif cmd == "start_session":
                gdb_path = self._resolve_gdb_path(request.get("gdb_path", "gdb"))
                wd = request.get("working_dir") or os.getcwd()
                working_dir = Path(wd).resolve()
                if not working_dir.exists():
                    raise FileNotFoundError(f"Working directory not found: {working_dir}")

                session_id = uuid.uuid4().hex[:8]
                session = GdbSession.start(
                    session_id=session_id,
                    working_dir=working_dir,
                    gdb_path=gdb_path,
                    startup_timeout=request.get("startup_timeout", 10.0),
                )
                with self._lock:
                    self.sessions[session_id] = session
                return {"ok": True, "data": session.to_dict()}

            elif cmd == "execute":
                session_id = request.get("session_id")
                command = request.get("command")
                timeout = request.get("timeout", 90.0)
                max_length = request.get("max_length")  # None if not specified
                session = self._get_session(session_id)
                result = session.execute(command, timeout=timeout, max_length=max_length)
                return {"ok": True, "data": result}

            elif cmd == "interrupt":
                session_id = request.get("session_id")
                timeout = request.get("timeout", 5.0)
                session = self._get_session(session_id)
                output = session.interrupt()
                return {"ok": True, "data": {"output": output}}

            elif cmd == "get_state":
                session_id = request.get("session_id")
                session = self._get_session(session_id)
                return {"ok": True, "data": session.to_dict()}

            elif cmd == "terminate_session":
                session_id = request.get("session_id")
                with self._lock:
                    session = self.sessions.pop(session_id, None)
                if session:
                    session.terminate()
                return {"ok": True, "data": {"status": "terminated"}}

            elif cmd == "list_sessions":
                with self._lock:
                    sessions = [s.to_dict() for s in self.sessions.values()]
                return {"ok": True, "data": {"sessions": sessions, "count": len(sessions)}}

            elif cmd == "shutdown":
                result = self.shutdown()
                return {"ok": True, "data": result}

            else:
                return {"ok": False, "error": f"Unknown command: {cmd}"}

        except TimeoutError as e:
            return {"ok": False, "error": str(e), "hint": "Use 'interrupt' to stop running program"}
        except FileNotFoundError as e:
            return {"ok": False, "error": str(e)}
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single client connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            if data:
                request = json.loads(data.decode())
                response = self.handle_request(request)
                conn.send(json.dumps(response).encode())
        except Exception as e:
            try:
                conn.send(json.dumps({"ok": False, "error": str(e)}).encode())
            except:
                pass
        finally:
            conn.close()

    def run(self) -> None:
        """Main server loop."""
        print(f"GDB RPC server listening on {self.socket_path}")
        print(f"Idle timeout: {self.idle_timeout}s ({self.idle_timeout/60:.1f} min)")

        while self._running:
            try:
                conn, addr = self.sock.accept()
                thread = threading.Thread(target=self._handle_connection, args=(conn,))
                thread.start()
            except socket.timeout:
                # Periodic cleanup check
                now = time.time()
                if now - self._last_cleanup_check >= CLEANUP_INTERVAL:
                    self._cleanup_idle_sessions()
                    self._last_cleanup_check = now
                continue
            except Exception as e:
                if self._running:
                    print(f"Socket error: {e}")

        self.sock.close()
        self.terminate_all()

    def terminate_all(self) -> None:
        """Terminate all sessions."""
        with self._lock:
            for session in list(self.sessions.values()):
                try:
                    session.terminate()
                except:
                    pass
            self.sessions.clear()


def main():
    parser = argparse.ArgumentParser(description="GDB RPC Server Daemon")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Base directory")
    parser.add_argument("--socket", default=None, help="Socket path")
    parser.add_argument("--idle-timeout", type=int, default=None,
                        help="Idle timeout in seconds (default: 3600 = 60 min)")
    args = parser.parse_args()

    # Priority: CLI arg > env var > default
    idle_timeout = args.idle_timeout
    if idle_timeout is None:
        idle_timeout = int(os.environ.get("GDB_CLI_IDLE_TIMEOUT", DEFAULT_IDLE_TIMEOUT))

    base_dir = Path(args.base_dir)
    socket_path = Path(args.socket) if args.socket else base_dir / DEFAULT_SOCKET_NAME

    server = GDBServer(socket_path, idle_timeout=idle_timeout)
    server.run()


if __name__ == "__main__":
    main()