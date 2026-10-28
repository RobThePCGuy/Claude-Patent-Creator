"""Non-patent literature search (Firecrawl) without network or a real key.

urlopen is replaced by a stub, so these tests check what is sent, how both
response shapes are parsed, and that failures never leak the key or read as
"no results".
"""

import asyncio
import io
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_server"))

import firecrawl_search  # noqa: E402
from firecrawl_search import FirecrawlNotConfiguredError, FirecrawlSearch  # noqa: E402

KEY = "fc-test-key-123"


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub(monkeypatch, body=None, error=None):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if error is not None:
            raise error
        return _Response(json.dumps(body).encode())

    monkeypatch.setattr(firecrawl_search.urllib.request, "urlopen", fake_urlopen)
    return calls


def _http_error(code, payload=None):
    fp = io.BytesIO(json.dumps(payload).encode() if payload is not None else b"oops")
    return urllib.error.HTTPError(firecrawl_search.ENDPOINT, code, "err", {}, fp)


def test_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    calls = _stub(monkeypatch, body={})
    searcher = FirecrawlSearch()
    assert not searcher.is_configured()
    with pytest.raises(FirecrawlNotConfiguredError, match="FIRECRAWL_API_KEY"):
        searcher.search("anything")
    assert calls == []


def test_key_read_from_environment(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", f"  {KEY} ")
    assert FirecrawlSearch().api_key == KEY


def test_request_shape(monkeypatch):
    calls = _stub(monkeypatch, body={"success": True, "data": {"web": []}})
    FirecrawlSearch(api_key=KEY).search("dendrite suppression", limit=50)
    request = calls[0]
    assert request.full_url == "https://api.firecrawl.dev/v2/search"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {KEY}"
    assert json.loads(request.data) == {
        "query": "dendrite suppression",
        "limit": 20,
        "origin": "Claude-Patent-Creator",
        "categories": ["research"],
    }


def test_whole_web_drops_category(monkeypatch):
    calls = _stub(monkeypatch, body={"success": True, "data": {"web": []}})
    FirecrawlSearch(api_key=KEY).search("q", limit=3, research_only=False)
    assert "categories" not in json.loads(calls[0].data)


def test_parses_web_results(monkeypatch):
    _stub(
        monkeypatch,
        body={
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://example.org/paper",
                        "title": " Lithium Dendrite Growth ",
                        "description": "Ceramic electrolytes suppress dendrites.",
                        "position": 1,
                        "category": "research",
                    }
                ]
            },
        },
    )
    assert FirecrawlSearch(api_key=KEY).search("q") == [
        {
            "title": "Lithium Dendrite Growth",
            "url": "https://example.org/paper",
            "snippet": "Ceramic electrolytes suppress dendrites.",
            "source": "research",
        }
    ]


def test_parses_research_index_results(monkeypatch):
    papers = [
        {"primaryId": "arxiv:2105.05233", "title": "Diffusion Models", "abstract": "We show"},
        {"primaryId": "pmid:123", "title": "B", "abstract": ""},
        {"primaryId": "doi:10.1000/xyz", "title": "C"},
        {"primaryId": "other:1", "title": "D"},
    ]
    _stub(monkeypatch, body={"success": True, "data": {"research": papers}})
    results = FirecrawlSearch(api_key=KEY).search("q", limit=10)
    assert [r["url"] for r in results] == [
        "https://arxiv.org/abs/2105.05233",
        "https://pubmed.ncbi.nlm.nih.gov/123/",
        "https://doi.org/10.1000/xyz",
        None,
    ]
    assert results[0] == {
        "title": "Diffusion Models",
        "url": "https://arxiv.org/abs/2105.05233",
        "snippet": "We show",
        "id": "arxiv:2105.05233",
        "source": "research_index",
    }


def test_limit_applies_across_both_shapes(monkeypatch):
    body = {
        "success": True,
        "data": {
            "research": [{"primaryId": "arxiv:1", "title": "a"}],
            "web": [{"url": "https://x", "title": "b"}, {"url": "https://y", "title": "c"}],
        },
    }
    _stub(monkeypatch, body=body)
    assert [r["title"] for r in FirecrawlSearch(api_key=KEY).search("q", limit=2)] == ["a", "b"]


def test_http_error_raises_and_redacts(monkeypatch):
    _stub(monkeypatch, error=_http_error(500, {"error": f"boom {KEY}"}))
    with pytest.raises(RuntimeError) as exc:
        FirecrawlSearch(api_key=KEY).search("q")
    assert "HTTP 500" in str(exc.value)
    assert KEY not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


def test_unauthorized_is_a_setup_error(monkeypatch):
    _stub(monkeypatch, error=_http_error(401, {"error": "Unauthorized: Invalid token"}))
    with pytest.raises(FirecrawlNotConfiguredError, match="HTTP 401"):
        FirecrawlSearch(api_key=KEY).search("q")


def test_network_error_redacts_key(monkeypatch):
    _stub(monkeypatch, error=OSError(f"connection reset while sending {KEY}"))
    with pytest.raises(RuntimeError) as exc:
        FirecrawlSearch(api_key=KEY).search("q")
    assert KEY not in str(exc.value) and "***" in str(exc.value)


def test_unsuccessful_body_is_an_error_not_empty(monkeypatch):
    _stub(monkeypatch, body={"success": False, "error": "Insufficient credits"})
    with pytest.raises(RuntimeError, match="Insufficient credits"):
        FirecrawlSearch(api_key=KEY).search("q")


def test_unreadable_body(monkeypatch):
    def fake_urlopen(request, timeout):
        return _Response(b"<html>")

    monkeypatch.setattr(firecrawl_search.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="unreadable"):
        FirecrawlSearch(api_key=KEY).search("q")


def _register_tool():
    from firecrawl_tools import register_firecrawl_tools
    from validation import SearchNonPatentLiteratureInput, validate_input

    registered = {}

    def tool():
        def decorator(fn):
            registered[fn.__name__] = fn
            return fn

        return decorator

    register_firecrawl_tools(
        mcp=SimpleNamespace(tool=tool),
        log_info=lambda *a, **k: None,
        log_error=lambda *a, **k: None,
        validate_input=validate_input,
        SearchNonPatentLiteratureInput=SearchNonPatentLiteratureInput,
        track_performance=lambda name: lambda fn: fn,
    )
    return registered["search_non_patent_literature"]


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parent.parent / "mcp_server" / "tools")
    )
    return _register_tool()


def test_tool_returns_setup_message_without_key(monkeypatch, tool):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    calls = _stub(monkeypatch, body={})
    result = asyncio.run(tool(query="solid electrolyte"))
    assert len(result) == 1 and "FIRECRAWL_API_KEY" in result[0]["error"]
    assert calls == []


def test_tool_rejects_invalid_input(tool):
    result = asyncio.run(tool(query="q", limit=0))
    assert result[0]["error"].startswith("Invalid input")


def test_tool_returns_results(monkeypatch, tool):
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    _stub(
        monkeypatch, body={"success": True, "data": {"web": [{"url": "https://x", "title": "t"}]}}
    )
    result = asyncio.run(tool(query="q", limit=1))
    assert result == [{"title": "t", "url": "https://x", "snippet": "", "source": "web"}]


def test_tool_reports_failures_as_errors(monkeypatch, tool):
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    _stub(monkeypatch, error=_http_error(502))
    result = asyncio.run(tool(query="q"))
    assert result == [{"error": "Firecrawl search failed: HTTP 502"}]


def test_out_of_credits_message(monkeypatch):
    _stub(monkeypatch, error=_http_error(402, {"error": "Insufficient credits"}))
    with pytest.raises(RuntimeError, match="out of Firecrawl credits"):
        FirecrawlSearch(api_key=KEY).search("q")


def test_tool_rejects_blank_query(monkeypatch, tool):
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    calls = _stub(monkeypatch, body={})
    result = asyncio.run(tool(query="   "))
    assert result[0]["error"].startswith("Invalid input")
    assert calls == []


def test_tool_explains_empty_research_results(monkeypatch, tool):
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    _stub(monkeypatch, body={"success": True, "data": {"research": []}})
    result = asyncio.run(tool(query="q"))
    assert len(result) == 1 and "research_only=False" in result[0]["message"]


def test_tool_returns_empty_list_for_empty_web_results(monkeypatch, tool):
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    _stub(monkeypatch, body={"success": True, "data": {"web": []}})
    assert asyncio.run(tool(query="q", research_only=False)) == []


def test_health_check_reports_optional_key_without_affecting_score(monkeypatch):
    try:
        from health_check import SystemHealthChecker
    except ImportError:
        from mcp_server.health_check import SystemHealthChecker

    checker = SystemHealthChecker()
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    missing = checker._check_non_patent_literature()
    assert missing["status"] == "not_configured" and "ready" not in missing
    assert "FIRECRAWL_API_KEY" in missing["fix"]
    monkeypatch.setenv("FIRECRAWL_API_KEY", KEY)
    assert checker._check_non_patent_literature()["status"] == "configured"
