#!/usr/bin/env python3
"""Opt-in stdio workaround for anthropics/claude-code#96183.

Reject only server/discover so affected clients initialize in legacy mode.
All other lines pass unchanged. Requires only Python's standard library.
Remove this wrapper once the client's negotiation bug is fixed.
"""

import argparse
import json
import subprocess
import sys
import threading
from contextlib import suppress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- server command and args")
    command = parser.parse_args().command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("provide -- followed by the MCP server command")
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    except OSError as exc:
        parser.exit(1, f"Cannot start MCP server: {exc}\n")
    output_lock = threading.Lock()

    def write_output(line):
        with output_lock:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    def forward_input():
        try:
            for line in sys.stdin.buffer:
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    message = None
                if isinstance(message, dict) and message.get("method") == "server/discover":
                    if "id" in message:
                        reply = {"jsonrpc": "2.0", "id": message["id"],
                                 "error": {"code": -32601, "message": "Method not found"}}
                        write_output(json.dumps(reply).encode("utf-8") + b"\n")
                    continue
                child.stdin.write(line)
                child.stdin.flush()
        except (BrokenPipeError, OSError):
            pass  # The child has exited; main preserves its exit status.
        finally:
            with suppress(BrokenPipeError, OSError):
                child.stdin.close()

    threading.Thread(target=forward_input, daemon=True).start()
    try:
        for line in child.stdout:
            write_output(line)
        return child.wait()
    except (KeyboardInterrupt, BrokenPipeError):
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        return 1


if __name__ == "__main__":
    sys.exit(main())
