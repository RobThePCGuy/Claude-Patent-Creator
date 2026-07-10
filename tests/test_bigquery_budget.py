"""Tests for the BigQuery per-query cost-budget guard.

These verify that an over-budget query fails fast with an actionable error
(via a free dry-run estimate) AND that the guarantee holds when the dry run
is unavailable: a real query rejected by BigQuery's maximum_bytes_billed is
translated into the same actionable error. Mocked client — no credentials
or network.
"""

from unittest.mock import MagicMock

import pytest

from mcp_server.bigquery_search import (
    BigQueryBudgetExceededError,
    BigQueryPatentSearch,
)


def _searcher(dry_estimate=None, query_side_effect=None, result_side_effect=None):
    """Build a BigQueryPatentSearch with a mocked client, bypassing __init__.

    dry_estimate: total_bytes_processed reported by every job object.
    query_side_effect: raise from client.query itself (kills the dry run).
    result_side_effect: raise from job.result() (kills the real query only).
    """
    searcher = object.__new__(BigQueryPatentSearch)
    client = MagicMock()
    if query_side_effect is not None:
        client.query.side_effect = query_side_effect
    else:
        job = client.query.return_value
        job.total_bytes_processed = dry_estimate
        if result_side_effect is not None:
            job.result.side_effect = result_side_effect
        else:
            job.result.return_value = iter([])
    searcher.client = client
    return searcher


@pytest.fixture(autouse=True)
def _hermetic_config(monkeypatch, tmp_path):
    """Isolate tests from the developer's real env var and config file."""
    monkeypatch.delenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", raising=False)
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))


def test_budget_guard_raises_specific_type_when_estimate_exceeds_cap():
    over = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 10
    searcher = _searcher(dry_estimate=over)

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher._assert_within_budget("SELECT 1", [])

    msg = str(exc.value)
    assert "per-query cost cap" in msg
    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in msg


def test_budget_guard_allows_query_within_cap():
    under = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED // 2
    searcher = _searcher(dry_estimate=under)

    searcher._assert_within_budget("SELECT 1", [])


def test_budget_guard_respects_env_override(monkeypatch):
    estimate = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 2
    searcher = _searcher(dry_estimate=estimate)

    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", str(estimate * 2))
    searcher._assert_within_budget("SELECT 1", [])

    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", str(estimate // 2))
    with pytest.raises(BigQueryBudgetExceededError):
        searcher._assert_within_budget("SELECT 1", [])


def test_env_below_schema_minimum_falls_back_to_default(monkeypatch):
    """The config schema rejects caps under 1 GiB; the resolver must agree
    instead of silently accepting a 5-byte cap that kills every query."""
    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", "5")
    searcher = _searcher(dry_estimate=1)

    assert searcher._resolve_max_bytes_billed() == BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED


def test_config_file_value_respected(tmp_path):
    """Documented resolution order is env > config file > default; with no
    env var set, the config-file value must win over the default."""
    two_gib = 2 * 1024**3
    (tmp_path / "config.json").write_text(f'{{"PATENT_BIGQUERY_MAX_BYTES_BILLED": "{two_gib}"}}')
    searcher = _searcher(dry_estimate=1)

    assert searcher._resolve_max_bytes_billed() == two_gib


def test_budget_guard_silent_when_estimate_unavailable():
    """A failed dry run must not block the real query from running."""
    searcher = _searcher(query_side_effect=RuntimeError("dry run failed"))

    searcher._assert_within_budget("SELECT 1", [])


def test_dry_run_is_time_bounded():
    """The pre-flight must not reintroduce unbounded hangs: the dry-run API
    call carries the same timeout as the real query."""
    searcher = _searcher(dry_estimate=1)

    searcher._assert_within_budget("SELECT 1", [])

    _, kwargs = searcher.client.query.call_args
    assert kwargs.get("timeout") == BigQueryPatentSearch.QUERY_TIMEOUT_SECONDS


def test_dry_run_does_not_disable_query_cache():
    """Cache-served re-runs bill 0 bytes and are exempt from the cap; the
    dry run must not force a worst-case uncached estimate."""
    searcher = _searcher(dry_estimate=1)

    searcher._assert_within_budget("SELECT 1", [])

    _, kwargs = searcher.client.query.call_args
    assert kwargs["job_config"].use_query_cache is not False


def test_real_query_cap_rejection_translated():
    """When the dry run passes (or is skipped) but BigQuery rejects the real
    query on maximum_bytes_billed, the opaque error must be translated into
    the same actionable BigQueryBudgetExceededError."""
    searcher = _searcher(
        dry_estimate=1,
        result_side_effect=Exception(
            "403 Query exceeded limit for bytes billed: 375809638400. "
            "reason: bytesBilledLimitExceeded"
        ),
    )

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher._run_query("SELECT 1", [])

    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in str(exc.value)


def test_real_query_other_errors_not_translated():
    searcher = _searcher(dry_estimate=1, result_side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        searcher._run_query("SELECT 1", [])


def test_get_patent_details_surfaces_budget_error():
    over = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 10
    searcher = _searcher(dry_estimate=over)

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher.get_patent_details("US1234567B2")

    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in str(exc.value)


def test_get_patent_details_surfaces_infrastructure_errors():
    """Auth/network/config failures must not masquerade as 'patent not
    found': they propagate instead of collapsing into None."""
    searcher = _searcher(dry_estimate=1, result_side_effect=RuntimeError("auth expired"))

    with pytest.raises(RuntimeError):
        searcher.get_patent_details("US1234567B2")


def test_keyword_budget_error_carries_narrowing_hint():
    over = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 10
    searcher = _searcher(dry_estimate=over)

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher.search_by_keywords("neural network")

    assert "start_year" in str(exc.value)


def test_family_budget_error_omits_keyword_hint():
    """Remediation advice must match the query shape: family search has no
    keyword/year filters, so the error must not suggest them."""
    over = BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED * 10
    searcher = _searcher(dry_estimate=over)

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher.search_patent_family(12345)

    msg = str(exc.value)
    assert "start_year" not in msg
    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in msg


def test_sub_gib_amounts_do_not_render_as_zero(monkeypatch):
    """With a small cap, the message must not read '0 GiB exceeding 0 GiB'."""
    monkeypatch.setenv("PATENT_BIGQUERY_MAX_BYTES_BILLED", str(2 * 1024**3))
    searcher = _searcher(dry_estimate=3 * 1024**3 + 512 * 1024**2)  # 3.5 GiB

    with pytest.raises(BigQueryBudgetExceededError) as exc:
        searcher._assert_within_budget("SELECT 1", [])

    assert "~0 GiB" not in str(exc.value)


def test_format_date_handles_zero_string():
    """BigQuery SQL casts dates to STRING, so a missing grant date arrives
    as '0' — it must render as None, not the string '0'."""
    searcher = object.__new__(BigQueryPatentSearch)
    assert searcher._format_date("0") is None
    assert searcher._format_date(0) is None
    assert searcher._format_date("20210101") == "2021-01-01"
