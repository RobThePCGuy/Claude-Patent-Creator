"""Tests for the BigQuery per-query cost-budget pre-flight guard.

These verify that an over-budget query fails fast with an actionable error
(via a free dry-run estimate) instead of being rejected mid-flight by BigQuery
or appearing to hang. They use a mocked client, so no credentials or network.
"""

from unittest.mock import MagicMock

import pytest

from mcp_server.bigquery_search import BigQueryPatentSearch


def _searcher_with_estimate(estimated_bytes):
    """Build a BigQueryPatentSearch whose dry run reports a fixed scan size,
    bypassing real credentials/network (skips __init__)."""
    searcher = object.__new__(BigQueryPatentSearch)
    client = MagicMock()
    client.query.return_value.total_bytes_processed = estimated_bytes
    searcher.client = client
    return searcher


def test_budget_guard_raises_when_estimate_exceeds_cap(monkeypatch):
    monkeypatch.delenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", raising=False)
    over = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 10
    searcher = _searcher_with_estimate(over)

    with pytest.raises(ValueError) as exc:
        searcher._assert_within_budget("SELECT 1", [])

    msg = str(exc.value)
    # The error is actionable: it names the cap, the override knob, and a remedy.
    assert "per-query cost cap" in msg
    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in msg


def test_budget_guard_allows_query_within_cap(monkeypatch):
    monkeypatch.delenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", raising=False)
    under = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED // 2
    searcher = _searcher_with_estimate(under)

    # Within budget -> no exception.
    searcher._assert_within_budget("SELECT 1", [])


def test_budget_guard_respects_env_override(monkeypatch):
    estimate = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 2
    searcher = _searcher_with_estimate(estimate)

    # Cap raised above the estimate -> allowed.
    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", str(estimate * 2))
    searcher._assert_within_budget("SELECT 1", [])

    # Cap lowered below the estimate -> blocked.
    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", str(estimate // 2))
    with pytest.raises(ValueError):
        searcher._assert_within_budget("SELECT 1", [])


def test_budget_guard_silent_when_estimate_unavailable(monkeypatch):
    """A failed dry run must not block the real query from running."""
    monkeypatch.delenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", raising=False)
    searcher = object.__new__(BigQueryPatentSearch)
    client = MagicMock()
    client.query.side_effect = RuntimeError("dry run failed")
    searcher.client = client

    # Swallows the dry-run failure and returns without raising.
    searcher._assert_within_budget("SELECT 1", [])
