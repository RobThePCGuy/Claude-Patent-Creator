"""The MCP server speaks JSON-RPC over stdout, so importing the modules it
loads at startup must not print anything there.

PyMuPDF's legacy ``import fitz`` prints a deprecation warning to stdout; the
MCP client then receives it as an invalid message ahead of the handshake.
"""

import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "mcp_server"


def test_importing_mpep_search_writes_nothing_to_stdout():
    # Bare-module import with mcp_server/ on sys.path, as server.py runs.
    code = f"import sys; sys.path.insert(0, {str(PKG)!r}); import mpep_search"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"stdout must stay empty for MCP stdio: {result.stdout!r}"
