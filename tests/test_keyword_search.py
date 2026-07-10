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


class TestTokenizer:
    def test_multiword_splits_into_terms(self):
        assert BigQueryPatentSearch._tokenize_query("blockchain authentication") == [
            "blockchain",
            "authentication",
        ]

    def test_boolean_operators_and_parens_are_dropped(self):
        # The skill used to recommend this exact form; it must degrade to terms.
        assert BigQueryPatentSearch._tokenize_query(
            "blockchain AND (authentication OR verification)"
        ) == ["blockchain", "authentication", "verification"]

    def test_quoted_phrase_is_preserved(self):
        assert BigQueryPatentSearch._tokenize_query('"wireless power" implant') == [
            "wireless power",
            "implant",
        ]

    def test_duplicates_removed_and_lowercased(self):
        assert BigQueryPatentSearch._tokenize_query("Sensor sensor SENSOR") == ["sensor"]

    def test_operator_only_input_is_empty(self):
        assert BigQueryPatentSearch._tokenize_query("AND OR ()") == []


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
    def test_each_term_becomes_its_own_anded_group(self):
        client = _run(
            "blockchain authentication", country="US", search_fields=["title", "abstract"]
        )
        term_params = {p.name: p.value for p in client.params if p.name.startswith("term")}
        assert term_params == {"term0": "%blockchain%", "term1": "%authentication%"}

        where = client.sql.split("WHERE", 1)[1].split("ORDER BY")[0]
        # AND across terms, OR across fields within a term.
        assert "LIKE @term0 OR" in where and "LIKE @term1 OR" in where
        assert ") AND (" in where

    def test_results_ranked_by_relevance(self):
        client = _run("wireless sensor", country="US", search_fields=["title"])
        assert "AS relevance_score" in client.sql
        assert "ORDER BY relevance_score DESC" in client.sql

    def test_title_weighted_above_abstract_in_score(self):
        client = _run("sensor", country="US", search_fields=["title", "abstract"])
        # Title contributes 3, abstract 1, to the relevance score.
        assert "THEN 3 ELSE 0 END" in client.sql
        assert "THEN 1 ELSE 0 END" in client.sql

    def test_claims_field_only_used_for_us(self):
        us = _run("sensor", country="US", search_fields=["claims"])
        assert "claims_localized" in us.sql
        # Non-US has no claims full-text here. A claims-only search on EP must not
        # emit a predicate-less query that scans everything — it returns nothing
        # without ever touching BigQuery.
        ep = _run("sensor", country="EP", search_fields=["claims"])
        assert ep.sql is None

    def test_like_metacharacters_are_escaped(self):
        # % and _ are LIKE wildcards; a literal term must be escaped so it does
        # not match unintended rows (a stray "%" would otherwise match everything).
        client = _run("50%_off", country="US", search_fields=["title"])
        term_values = [p.value for p in client.params if p.name.startswith("term")]
        assert term_values == ["%50\\%\\_off%"]

    def test_empty_query_issues_no_query(self):
        client = _run("", country="US")
        assert client.sql is None

    def test_operator_only_query_issues_no_query(self):
        client = _run("and or ( )", country="US")
        assert client.sql is None
