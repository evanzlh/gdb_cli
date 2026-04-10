"""End-to-end tests for GDB CLI."""

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
    int x = 42;
    printf("x = %d\\n", x);
    return x;
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


class TestE2E:
    """End-to-end tests for complete debugging workflows."""

    def test_basic_debug_session(self, server_process, simple_binary: Path):
        """Test basic debug session: start -> file -> breakpoint -> run -> backtrace -> terminate."""
        # Start session
        result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        session_id = data["session_id"]

        # Load binary
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, f"file {simple_binary}"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

        # Set breakpoint at main
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "break main"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

        # Start program
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "starti", "--timeout", "10"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

        # Get backtrace
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "bt"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "frames" in data or "output" in data

        # Step through code
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "next", "--timeout", "5"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

        # Print a variable
        result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "print x"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

        # Terminate session
        result = subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_continue_hits_breakpoint(self, server_process, tmp_path: Path):
        """Test that continue properly blocks until breakpoint is hit."""
        # Create a program with a loop
        c_file = tmp_path / "loop.c"
        c_file.write_text("""
#include <stdio.h>
int counter = 0;
void increment() {
    counter++;
}
int main() {
    for (int i = 0; i < 100; i++) {
        increment();
    }
    return counter;
}
""")
        binary = tmp_path / "loop_test"
        result = subprocess.run(
            ["gcc", "-g", str(c_file), "-o", str(binary)],
            capture_output=True,
        )
        if result.returncode != 0:
            pytest.skip("gcc not available")

        # Start session
        start_result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True, text=True,
        )
        session_id = json.loads(start_result.stdout)["session_id"]

        # Load binary
        subprocess.run(
            ["gdb-cli", "command", "--session", session_id, f"file {binary}"],
            capture_output=True, text=True,
        )

        # Set breakpoint at increment with condition
        bp_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id,
             "break increment if counter == 50"],
            capture_output=True, text=True,
        )
        assert bp_result.returncode == 0

        # Start program
        start_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "start", "--timeout", "10"],
            capture_output=True, text=True,
        )
        assert start_result.returncode == 0

        # Continue - should hit breakpoint when counter == 50
        continue_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "continue", "--timeout", "30"],
            capture_output=True, text=True,
        )
        assert continue_result.returncode == 0

        # Backtrace should work
        bt_result = subprocess.run(
            ["gdb-cli", "command", "--session", session_id, "bt"],
            capture_output=True, text=True,
        )
        assert bt_result.returncode == 0
        bt_data = json.loads(bt_result.stdout)
        output = bt_data.get("output", "")
        frames = bt_data.get("frames", [])
        assert len(frames) > 0 or "No stack" not in output

        # Cleanup
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True, text=True,
        )

    def test_session_persistence(self, server_process):
        """Test that session persists across multiple commands."""
        # Start session
        result = subprocess.run(
            ["gdb-cli", "start"],
            capture_output=True, text=True,
        )
        session_id = json.loads(result.stdout)["session_id"]

        # List sessions
        result = subprocess.run(
            ["gdb-cli", "sessions"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        assert session_id in [s["session_id"] for s in data["sessions"]]

        # Execute multiple commands
        for cmd in ["help", "show version", "info sources"]:
            result = subprocess.run(
                ["gdb-cli", "command", "--session", session_id, cmd],
                capture_output=True, text=True,
            )
            assert result.returncode == 0

        # Session should still exist
        result = subprocess.run(
            ["gdb-cli", "sessions"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        assert session_id in [s["session_id"] for s in data["sessions"]]

        # Terminate
        subprocess.run(
            ["gdb-cli", "terminate", "--session", session_id],
            capture_output=True, text=True,
        )

        # Session should be gone
        result = subprocess.run(
            ["gdb-cli", "sessions"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        assert session_id not in [s["session_id"] for s in data["sessions"]]