"""Regression tests for keyword prior-art search query construction.

The original search matched the entire query as one substring
(``LIKE '%multi word query%'``) and ordered by recency, so a normal
multi-word query required a verbatim phrase (≈8% recall in practice) and
Boolean-style input matched literally (0 hits). search_by_keywords now
splits the query into terms (AND across terms, OR across fields) and ranks
by a relevance score, so these tests pin both the tokenizer and the
generated SQL without needing live BigQuery.
"""

from mcp_server.bigquery_search import BigQueryPatentSearch


class _FakeQueryJob:
    # Dry runs read total_bytes_processed off the job itself; keep it present
    # so these tests exercise the budget guard instead of tripping its
    # degrade-open exception path.
    total_bytes_processed = 0

    def __init__(self):
        class _Result(list):
            total_bytes_processed = 0
            total_bytes_billed = 0

        self._result = _Result()

    def result(self, timeout=None):
        return self._result


class _FakeClient:
    def __init__(self):
        self.sql = None
        self.params = None

    def query(self, sql, job_config=None, timeout=None):
        self.sql = sql
        self.params = job_config.query_parameters
        return _FakeQueryJob()


def _run(query, **kwargs):
    searcher = object.__new__(BigQueryPatentSearch)
    searcher.client = _FakeClient()
    searcher.search_by_keywords(query, **kwargs)
    return searcher.client


class TestGeneratedSQL:
    def test_claims_field_only_used_for_us(self):
        # Non-US has no claims full-text here. A claims-only search on EP must not
        # emit a predicate-less query that scans everything — it returns nothing
        # without ever touching BigQuery.
        ep = _run("sensor", country="EP", search_fields=["claims"])
        assert ep.sql is None

    def test_empty_query_issues_no_query(self):
        client = _run("", country="US")
        assert client.sql is None

    def test_operator_only_query_issues_no_query(self):
        client = _run("and or ( )", country="US")
        assert client.sql is None
