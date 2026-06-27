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


def _make_tool():
    mcp = _FakeMCP()
    patent_law_tools.register_patent_law_tools(
        mcp,
        mpep_index=_FakeIndex(),
        log_info=lambda *a, **k: None,
        log_error=lambda *a, **k: None,
        validate_input=None,
        SearchPatentLawInput=None,  # skip validation
        track_performance=lambda *a, **k: (lambda f: f),
    )
    return mcp.tools["search_patent_law"]


def test_jurisdiction_results_are_ranked_by_relevance():
    search_patent_law = _make_tool()

    results = search_patent_law(query="claim definiteness", jurisdiction="US", top_k=3)

    scores = [r["relevance_score"] for r in results]
    # Truncated to top_k and sorted by relevance descending.
    assert scores == [0.90, 0.70, 0.50]
    # The single highest-scoring hit must be first. Under the old "score" key
    # the no-op sort would have left MPEP (0.10, first source) at the top.
    assert results[0]["source"] == "35_USC"


def test_unknown_jurisdiction_is_rejected():
    search_patent_law = _make_tool()
    results = search_patent_law(query="x", jurisdiction="ZZ", top_k=5)
    assert len(results) == 1 and "error" in results[0]
