"""CLI tests."""

import json
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


@pytest.fixture
def simple_binary(tmp_path: Path) -> Path:
    """Create a simple test binary."""
    c_file = tmp_path / "test.c"
    c_file.write_text("""
#include <stdio.h>
int main(int argc, char *argv[]) {
    printf("Hello\\n");
    return 0;
}
""")
    binary = tmp_path / "test_binary"

    result = subprocess.run(
        ["gcc", "-g", str(c_file), "-o", str(binary)],
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip("gcc not available")
    return binary


class TestCLICommands:
    """Tests for CLI commands."""

    def test_start_command(self, server_process):
        """Test start command creates a session."""
        result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "session_id" in output
        assert output["status"] == "ready"

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", output["session_id"]],
            capture_output=True,
        )

    def test_command_exec(self, server_process, simple_binary: Path):
        """Test command execution."""
        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # Load binary via command
        subprocess.run(
            ["gdb-cli", "command", "--session", session_id, f"file {simple_binary}"],
            capture_output=True,
        )

        # Execute command
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "info breakpoints"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
        )

    def test_status_command(self, server_process):
        """Test status command."""
        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # Get status
        result = subprocess.run(
            ["gdb-cli", "status", "--session", session_id],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "state" in output

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
        )

    def test_sessions_command(self, server_process):
        """Test sessions command lists sessions."""
        # Start a session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # List sessions
        result = subprocess.run(
            ["gdb-cli", "sessions"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "sessions" in output
        assert output["count"] >= 1

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
        )

    def test_terminate_command(self, server_process):
        """Test terminate command."""
        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # Terminate
        result = subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] == "terminated"


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_debug_flow(self, server_process, simple_binary: Path):
        """Test complete debug flow: start -> file -> breakpoint -> run -> backtrace -> terminate."""
        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        assert start_result.returncode == 0
        session_id = json.loads(start_result.stdout)["session_id"]

        # Load binary
        file_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, f"file {simple_binary}"],
            capture_output=True,
            text=True,
        )
        assert file_result.returncode == 0

        # Set breakpoint
        bp_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "break main"],
            capture_output=True,
            text=True,
        )
        assert bp_result.returncode == 0

        # Run with start command (stops at main)
        run_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "start", "--timeout", "10"],
            capture_output=True,
            text=True,
        )
        assert run_result.returncode == 0

        # Backtrace
        bt_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "bt"],
            capture_output=True,
            text=True,
        )
        assert bt_result.returncode == 0
        bt_data = json.loads(bt_result.stdout)
        # Should have frames or output
        assert "frames" in bt_data or "output" in bt_data

        # Terminate
        terminate_result = subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
            text=True,
        )
        assert terminate_result.returncode == 0

    def test_continue_with_breakpoint(self, server_process, tmp_path: Path):
        """Test continue command hitting a breakpoint."""
        # Create a program with a loop
        c_file = tmp_path / "loop.c"
        c_file.write_text("""
#include <stdio.h>
int main() {
    int i;
    for (i = 0; i < 10; i++) {
        printf("i = %d\\n", i);
    }
    return 0;
}
""")
        binary = tmp_path / "loop"
        result = subprocess.run(
            ["gcc", "-g", str(c_file), "-o", str(binary)],
            capture_output=True,
        )
        if result.returncode != 0:
            pytest.skip("gcc not available")

        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True,
            text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # Load binary
        subprocess.run(
            ["gdb-cli", "command", "--session", session_id, f"file {binary}"],
            capture_output=True,
        )

        # Set breakpoint at loop iteration
        bp_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "break 6 if i == 5"],
            capture_output=True,
            text=True,
        )
        assert bp_result.returncode == 0

        # Start program
        start_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "start", "--timeout", "10"],
            capture_output=True,
            text=True,
        )
        assert start_result.returncode == 0

        # Continue (should hit breakpoint at i == 5)
        continue_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "continue", "--timeout", "15"],
            capture_output=True,
            text=True,
        )
        assert continue_result.returncode == 0

        # Check backtrace is available
        bt_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "bt"],
            capture_output=True,
            text=True,
        )
        assert bt_result.returncode == 0
        bt_data = json.loads(bt_result.stdout)
        # Should have frames (not "No stack")
        assert "frames" in bt_data or ("output" in bt_data and "No stack" not in bt_data.get("output", ""))

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True,
        )