"""Exercise the optional compatibility shim against a real stdio subprocess."""

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SHIM = Path(__file__).resolve().parents[1] / "scripts/legacy_handshake_shim.py"


def test_discovery_rejected_locally_and_legacy_messages_forwarded(tmp_path):
    child = tmp_path / "echo_server.py"
    child.write_text(
        "import sys\n"
        "for line in sys.stdin.buffer:\n"
        "    sys.stdout.buffer.write(line); sys.stdout.buffer.flush()\n"
    )
    messages = [
        {"jsonrpc": "2.0", "id": 0, "method": "server/discover"},
        {"jsonrpc": "2.0", "method": "server/discover"},
        {"jsonrpc": "2.0", "id": "probe", "method": "server/discover"},
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"x": "é"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    wire = [json.dumps(m, ensure_ascii=False) + "\n" for m in messages]
    run = subprocess.run(
        [sys.executable, str(SHIM), "--", sys.executable, str(child)],
        input="".join(wire), text=True, capture_output=True, timeout=10,
    )
    assert run.returncode == 0, run.stderr
    replies = [json.loads(line) for line in run.stdout.splitlines()]
    errors = [m for m in replies if "error" in m]
    assert {m["id"] for m in errors} == {0, "probe"}
    assert all(m["error"]["code"] == -32601 for m in errors)
    forwarded = [m for m in replies if "error" not in m]
    assert forwarded == messages[3:]
    assert "".join(line for line in run.stdout.splitlines(keepends=True)
                   if '"error"' not in line) == "".join(wire[3:])


def test_child_exit_code_and_stderr_are_preserved():
    run = subprocess.run(
        [sys.executable, str(SHIM), "--", sys.executable, "-c",
         "import sys; print('child failure', file=sys.stderr); sys.exit(7)"],
        input="", text=True, capture_output=True, timeout=10,
    )
    assert run.returncode == 7
    assert run.stdout == ""
    assert "child failure" in run.stderr


def test_child_exit_preserved_while_client_keeps_stdin_open():
    process = subprocess.Popen(
        [sys.executable, str(SHIM), "--", sys.executable, "-c",
         "import time; time.sleep(0.2); raise SystemExit(7)"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        # MCP clients keep this pipe open until the server has exited.
        process.wait(timeout=10)
        assert process.returncode == 7, process.stderr.read().decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()


def test_missing_command_is_actionable():
    run = subprocess.run([sys.executable, str(SHIM)], input="", text=True,
                         capture_output=True, timeout=10)
    assert run.returncode != 0
    assert "usage:" in run.stderr.lower()


def test_large_and_unterminated_messages_forwarded_without_changes():
    wire = json.dumps({"jsonrpc": "2.0", "id": 1, "payload": "é" * 100000},
                      ensure_ascii=False).encode() + b"\nlast unterminated line"
    run = subprocess.run(
        [sys.executable, str(SHIM), "--", sys.executable, "-u", "-c",
         "import sys\nfor line in sys.stdin.buffer: sys.stdout.buffer.write(line); sys.stdout.buffer.flush()"],
        input=wire, capture_output=True, timeout=10,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == wire


def test_discovery_then_initialize_with_real_mcp_sdk(tmp_path):
    pytest.importorskip("mcp.server.mcpserver")
    child = tmp_path / "mcp_server_fixture.py"
    child.write_text(
        "from mcp.server.mcpserver import MCPServer\n"
        "MCPServer('shim-integration').run()\n"
    )
    process = subprocess.Popen(
        [sys.executable, str(SHIM), "--", sys.executable, str(child)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    def request(message):
        process.stdin.write(json.dumps(message).encode() + b"\n")
        process.stdin.flush()
        # Windows select() cannot wait on subprocess pipes.
        replies = queue.Queue()
        threading.Thread(target=lambda: replies.put(process.stdout.readline()),
                         daemon=True).start()
        return json.loads(replies.get(timeout=10))

    try:
        reply = request({"jsonrpc": "2.0", "id": 1, "method": "server/discover"})
        assert reply["error"]["code"] == -32601
        reply = request({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "regression", "version": "1"},
        }})
        assert reply["id"] == 2
        assert reply["result"]["serverInfo"]["name"] == "shim-integration"
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
