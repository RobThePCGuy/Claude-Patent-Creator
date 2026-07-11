"""BigQuery client creation must never shell out to gcloud (the MCP hang).

Root cause of the "search stalls" bug: google.auth.default() falls back to
running `gcloud config config-helper` in a subprocess to discover a project
id the code already resolved. Inside an MCP stdio server (no console, pipes
for stdin/stdout) that child process blocks indefinitely — users see a
multi-minute stall or a dead server. Verified by faulthandler stack dump:
AnyIO worker thread stuck in google/auth/_cloud_sdk.py get_project_id →
subprocess communicate().

Fix under test: before creating the client, export what we already know
(GOOGLE_CLOUD_PROJECT, GOOGLE_APPLICATION_CREDENTIALS) so google.auth's
explicit-environment paths win and the subprocess fallback is unreachable.
"""

import pytest

from mcp_server.bigquery_search import (
    BigQueryPatentSearch,
    BigQueryQuotaExhaustedError,
)
from tests.test_bigquery_budget import _searcher


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))


def test_exports_resolved_project_when_absent(monkeypatch):
    import os

    BigQueryPatentSearch._prepare_auth_environment("my-project", None)

    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "my-project"


def test_never_overrides_existing_project(monkeypatch):
    import os

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "user-set")
    BigQueryPatentSearch._prepare_auth_environment("resolved-other", None)

    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "user-set"


def test_exports_adc_path_when_file_exists(monkeypatch, tmp_path):
    import os

    creds = tmp_path / "application_default_credentials.json"
    creds.write_text("{}")

    BigQueryPatentSearch._prepare_auth_environment("p", creds)

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(creds)


def test_no_adc_export_when_file_missing(monkeypatch, tmp_path):
    import os

    BigQueryPatentSearch._prepare_auth_environment("p", tmp_path / "does_not_exist.json")

    assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ


def test_free_tier_quota_error_is_actionable():
    """The sandbox's monthly free bytes run out after ~3 default searches;
    the raw 403 must become guidance, like the budget guard's errors."""
    searcher = _searcher(
        dry_estimate=1,
        result_side_effect=Exception(
            "403 Quota exceeded: Your project exceeded quota for free query "
            "bytes scanned. reason: quotaExceeded, location: unbilled.analysis"
        ),
    )

    with pytest.raises(BigQueryQuotaExhaustedError) as exc:
        searcher._run_query("SELECT 1", [])

    msg = str(exc.value)
    assert "free" in msg.lower()
    assert "billing" in msg.lower()
    assert "1st" in msg or "month" in msg.lower()
