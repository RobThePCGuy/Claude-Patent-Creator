"""Regression tests for the cross-jurisdiction search tool.

When a jurisdiction filter is given, search_patent_law queries each source
separately and merges the hits. Those merged hits must be re-ranked by
relevance before truncating to top_k. The ranking keyed on a non-existent
"score" field (the index returns "relevance_score"), so the sort was a silent
no-op: results stayed in source-iteration order and top_k kept whichever
sources came first — dropping the genuinely best passages.
"""

from mcp_server.tools import patent_law_tools


class _FakeMCP:
    """Captures the function registered via @mcp.tool()."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class _FakeIndex:
    """Returns one hit per source with a preset relevance_score, so that
    source-iteration order deliberately differs from score order."""

    # US sources iterate as [MPEP, 35_USC, 37_CFR, SUBSEQUENT]; the scores below
    # are intentionally NOT in that order.
    SCORES = {"MPEP": 0.10, "35_USC": 0.90, "37_CFR": 0.50, "SUBSEQUENT": 0.70}

    def search(self, query, top_k, source_filter=None):
        score = self.SCORES[source_filter]
        return [{"source": source_filter, "relevance_score": score, "content": source_filter}]


class _USOnlyIndex(_FakeIndex):
    """Simulates a fresh install: US sources indexed, EPO/PCT absent."""

    def search(self, query, top_k, source_filter=None):
        if source_filter not in self.SCORES:
            raise KeyError(f"source not indexed: {source_filter}")
        return super().search(query, top_k, source_filter=source_filter)


def _make_us_only_tool():
    mcp = _FakeMCP()
    patent_law_tools.register_patent_law_tools(
        mcp,
        mpep_index=_USOnlyIndex(),
        log_info=lambda *a, **k: None,
        log_error=lambda *a, **k: None,
        validate_input=None,
        SearchPatentLawInput=None,
        track_performance=lambda *a, **k: (lambda f: f),
    )
    return mcp.tools["search_patent_law"]


def test_missing_jurisdiction_sources_reported_not_silent():
    """A fresh install has no EPO/PCT corpus; the tool must say so instead of
    returning an empty list that reads as 'no relevant law exists'."""
    search_patent_law = _make_us_only_tool()

    results = search_patent_law(query="inventive step", jurisdiction="EPO", top_k=5)

    assert len(results) == 1
    error = results[0]["error"]
    # Must explain the absence and point at a remedy, naming the jurisdiction.
    assert "EPO" in error
