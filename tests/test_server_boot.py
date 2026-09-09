"""Boot contract for the MCP server.

Nothing else in the suite imports ``mcp_server/server.py``, so a dependency bump
that breaks the server at import time (mcp 2.0 removing ``FastMCP``, reported in
issue #78 and re-introduced by the auto-merged #82) passed CI green. This test
imports the real module under the pinned SDK, registers every tool module
against a fresh server, and lists what the SDK sees. The tool count is derived
from the source so a new tool never needs this file touched.
"""

import asyncio
import importlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "mcp_server"


def _decorated_tool_count() -> int:
    pattern = re.compile(r"^\s*@mcp\.tool\(", re.MULTILINE)
    return sum(
        len(pattern.findall(p.read_text(encoding="utf-8"))) for p in (PKG / "tools").glob("*.py")
    )


def test_server_imports_and_registers_every_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("PATENT_DATA_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(PKG))
    sys.modules.pop("server", None)
    server = importlib.import_module("server")

    from mcp.server.mcpserver import MCPServer

    fresh = MCPServer("boot-check")
    monkeypatch.setattr(server, "mcp", fresh)
    # Registration captures the index by closure and never touches it; a stub
    # with the three attributes the stats resource reads keeps this offline.
    monkeypatch.setattr(server, "mpep_index", SimpleNamespace(chunks=[], metadata=[], index=None))

    server._register_all_tools()

    tools = asyncio.run(fresh.list_tools())
    names = {t.name for t in tools}
    assert len(tools) == _decorated_tool_count(), sorted(names)
    for required in ("search_mpep", "review_patent_claims", "check_package", "search_patent_law"):
        assert required in names

    resources = asyncio.run(fresh.list_resources())
    assert {str(r.uri) for r in resources} == {"mpep://index/stats"}

    body = asyncio.run(fresh.read_resource("mpep://index/stats"))
    stats = json.loads(next(iter(body)).content)
    assert stats["total_chunks"] == 0 and stats["index_exists"] is False
