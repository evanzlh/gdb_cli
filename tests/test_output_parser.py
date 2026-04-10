"""Output parser tests."""

import pytest

from gdb_cli.output_parser import (
    parse_backtrace,
    parse_threads,
    parse_print,
    parse_registers,
    parse_breakpoints,
    parse_sharedlibrary,
    parse_disassemble,
    parse_output,
)


class TestBacktraceParser:
    """Tests for backtrace output parsing."""

    def test_parse_simple_backtrace(self):
        """Test parsing a simple backtrace."""
        output = """#0  main () at main.c:10
#1  0x0000555555555156 in _start ()"""
        result = parse_backtrace(output)
        assert len(result["frames"]) == 2
        assert result["frames"][0]["num"] == 0
        assert result["frames"][0]["function"] == "main"
        assert result["frames"][0]["file"] == "main.c"
        assert result["frames"][0]["line"] == 10

    def test_parse_backtrace_with_args(self):
        """Test parsing backtrace with function arguments."""
        output = """#0  compute (x=5, y=10) at compute.c:25
#1  process (data=0x555555555abc) at process.c:50
#2  main (argc=1, argv=0x7fffffffe123) at main.c:15"""
        result = parse_backtrace(output)
        assert len(result["frames"]) == 3
        assert result["frames"][0]["function"] == "compute"
        assert result["frames"][2]["function"] == "main"

    def test_parse_backtrace_with_address(self):
        """Test parsing backtrace with addresses."""
        output = """#0  0x0000555555555123 in foo () at foo.c:5
#1  0x0000555555555156 in bar ()"""
        result = parse_backtrace(output)
        assert len(result["frames"]) == 2
        assert "address" in result["frames"][0]

    def test_parse_empty_backtrace(self):
        """Test parsing empty backtrace."""
        result = parse_backtrace("")
        assert result["frames"] == []


class TestThreadsParser:
    """Tests for threads output parsing."""

    def test_parse_single_thread(self):
        """Test parsing single thread."""
        output = """  Id   Target Id         Frame
* 1    process 1234 "myapp"  main () at main.c:10"""
        result = parse_threads(output)
        assert len(result["threads"]) == 1
        assert result["threads"][0]["id"] == 1
        assert result["threads"][0]["target_id"] == "process 1234 \"myapp\""
        assert result["threads"][0]["current"] == True

    def test_parse_multiple_threads(self):
        """Test parsing multiple threads."""
        output = """  Id   Target Id         Frame
* 1    process 1234 "myapp"  main () at main.c:10
  2    process 1234 "myapp"  worker () at worker.c:25
  3    process 1234 "myapp"  (running)"""
        result = parse_threads(output)
        assert len(result["threads"]) == 3
        assert result["threads"][0]["current"] == True
        assert result["threads"][1]["current"] == False
        assert result["threads"][2]["state"] == "running"


class TestPrintParser:
    """Tests for print output parsing."""

    def test_parse_int(self):
        """Test parsing integer value."""
        output = "$1 = 42"
        result = parse_print(output)
        assert result["value"] == "42"
        assert result["var"] == "$1"

    def test_parse_string(self):
        """Test parsing string value."""
        output = "$2 = \"hello world\""
        result = parse_print(output)
        assert result["value"] == "\"hello world\""

    def test_parse_struct(self):
        """Test parsing struct value."""
        output = """$3 = {x = 10, y = 20, z = 30}"""
        result = parse_print(output)
        assert "x = 10" in result["value"]

    def test_parse_pointer(self):
        """Test parsing pointer value."""
        output = "$4 = (int *) 0x555555555abc"
        result = parse_print(output)
        assert "type" in result
        assert result["type"] == "int *"


class TestRegistersParser:
    """Tests for registers output parsing."""

    def test_parse_registers(self):
        """Test parsing register values."""
        output = """rax            0x555555555123   93824992234531
rbx            0x0              0
rcx            0x555555555abc   93824992235676"""
        result = parse_registers(output)
        assert len(result["registers"]) >= 3
        assert result["registers"][0]["name"] == "rax"
        assert result["registers"][0]["value"] == "0x555555555123"


class TestBreakpointsParser:
    """Tests for breakpoints output parsing."""

    def test_parse_single_breakpoint(self):
        """Test parsing single breakpoint."""
        output = """Num     Type           Disp Enb Address    What
1       breakpoint     keep y   0x0000555555555123 in main at main.c:10"""
        result = parse_breakpoints(output)
        assert len(result["breakpoints"]) == 1
        assert result["breakpoints"][0]["num"] == 1
        assert result["breakpoints"][0]["type"] == "breakpoint"
        assert result["breakpoints"][0]["enabled"] == True

    def test_parse_multiple_breakpoints(self):
        """Test parsing multiple breakpoints."""
        output = """Num     Type           Disp Enb Address    What
1       breakpoint     keep y   0x0000555555555123 in main at main.c:10
2       breakpoint     keep n   0x0000555555555156 in foo at foo.c:5
	breakpoint already hit 1 time"""
        result = parse_breakpoints(output)
        assert len(result["breakpoints"]) == 2
        assert result["breakpoints"][0]["enabled"] == True
        assert result["breakpoints"][1]["enabled"] == False


class TestSharedLibraryParser:
    """Tests for sharedlibrary output parsing."""

    def test_parse_sharedlibrary(self):
        """Test parsing shared library list."""
        output = """From                To                  Syms Read   Shared Object Library
0x00007ffff7dd0000  0x00007ffff7dd2000  Yes         /lib64/ld-linux-x86-64.so.2
0x00007ffff7fbc000  0x00007ffff7ffb000  Yes         /lib64/libc.so.6"""
        result = parse_sharedlibrary(output)
        assert len(result["libraries"]) == 2
        assert "/lib64/ld-linux-x86-64.so.2" in result["libraries"][0]["name"]

    def test_parse_empty_sharedlibrary(self):
        """Test parsing empty shared library list."""
        result = parse_sharedlibrary("No shared libraries loaded at this time.")
        assert result["libraries"] == []


class TestDisassembleParser:
    """Tests for disassemble output parsing."""

    def test_parse_disassemble(self):
        """Test parsing disassembly output."""
        output = """   0x0000555555555123 <main+0>:	push   %rbp
   0x0000555555555124 <main+1>:	mov    %rsp,%rbp
   0x0000555555555127 <main+4>:	mov    $0x5,%eax"""
        result = parse_disassemble(output)
        assert len(result["instructions"]) == 3
        assert result["instructions"][0]["address"] == "0x0000555555555123"
        assert "push" in result["instructions"][0]["asm"]


class TestParseOutput:
    """Tests for generic parse_output function."""

    def test_parse_backtrace_command(self):
        """Test auto-detection of backtrace."""
        output = "#0  main () at main.c:10"
        result = parse_output("bt", output)
        assert "frames" in result

    def test_parse_threads_command(self):
        """Test auto-detection of threads."""
        output = "* 1    process 1234 \"myapp\" main ()"
        result = parse_output("info threads", output)
        assert "threads" in result

    def test_parse_unknown_command(self):
        """Test unknown command returns raw output."""
        output = "Some random output"
        result = parse_output("some_command", output)
        assert result["output"] == output