"""Server and client tests."""

import subprocess
import time
from pathlib import Path

import pytest

from gdb_cli.client import GDBClient, DEFAULT_BASE_DIR, DEFAULT_SOCKET_NAME


def has_gdb() -> bool:
    """Check if GDB is available."""
    try:
        result = subprocess.run(["gdb", "--version"], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


@pytest.fixture
def gdb_available():
    """Skip tests if GDB is not available."""
    if not has_gdb():
        pytest.skip("GDB not available")
    return True


@pytest.fixture
def server_process(gdb_available):
    """Start the GDB server for testing."""
    import os
    import signal

    socket_path = DEFAULT_BASE_DIR / DEFAULT_SOCKET_NAME

    # Clean up any existing socket
    if socket_path.exists():
        socket_path.unlink()

    # Start server
    proc = subprocess.Popen(
        ["gdb-cli-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for server to start
    client = GDBClient()
    for _ in range(20):
        time.sleep(0.2)
        try:
            result = client.ping()
            if result.get("ok"):
                break
        except:
            continue
    else:
        proc.kill()
        pytest.skip("Failed to start GDB server")

    yield proc

    # Cleanup
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except:
        proc.kill()
    proc.wait()


class TestGDBClient:
    """Tests for GDB client."""

    def test_ping(self, server_process):
        """Test ping."""
        client = GDBClient()
        result = client.ping()
        assert result.get("ok") == True

    def test_start_session(self, server_process):
        """Test starting a session."""
        client = GDBClient()
        result = client.start_session()
        assert result.get("ok") == True
        data = result.get("data", {})
        assert "session_id" in data
        assert data.get("alive") == True

        # Cleanup
        client.terminate_session(data["session_id"])

    def test_execute_command(self, server_process):
        """Test executing a command."""
        client = GDBClient()
        result = client.start_session()
        session_id = result["data"]["session_id"]

        result = client.execute(session_id, "help")
        assert result.get("ok") == True
        assert "output" in result.get("data", {})

        client.terminate_session(session_id)

    def test_list_sessions(self, server_process):
        """Test listing sessions."""
        client = GDBClient()

        # Start a session
        result = client.start_session()
        session_id = result["data"]["session_id"]

        # List sessions
        result = client.list_sessions()
        assert result.get("ok") == True
        data = result.get("data", {})
        assert data.get("count", 0) >= 1

        client.terminate_session(session_id)

    def test_terminate_session(self, server_process):
        """Test terminating a session."""
        client = GDBClient()

        result = client.start_session()
        session_id = result["data"]["session_id"]

        # Terminate
        result = client.terminate_session(session_id)
        assert result.get("ok") == True

        # Verify session is gone
        result = client.list_sessions()
        sessions = result.get("data", {}).get("sessions", [])
        assert session_id not in [s["session_id"] for s in sessions]