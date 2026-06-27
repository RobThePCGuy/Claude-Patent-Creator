"""Tests for USPTO ODP client helpers."""

from mcp_server.uspto_api import USPTOClient


def test_normalize_current_odp_search_response():
    """The real ODP search envelope is mapped onto the results/totalHits contract.

    The live ``applications/search`` envelope carries the total under
    ``totalNumFound`` and the records under ``patentFileWrapperDataBag``; there
    is no ``count`` key. A realistic paginated response returns far fewer
    records than the total, so ``totalHits`` must come from ``totalNumFound``,
    not from the length of the returned page.
    """
    raw = {
        "totalNumFound": 4231,
        "patentFileWrapperDataBag": [
            {
                "applicationNumberText": "18045436",
                "applicationMetaData": {
                    "patentNumber": "12000000",
                    "inventionTitle": "Labeled nucleotide analogs",
                },
            }
        ],
        "requestIdentifier": "request-id",
    }

    normalized = USPTOClient._normalize_search_response(raw)

    assert normalized["totalHits"] == 4231
    assert normalized["results"] == raw["patentFileWrapperDataBag"]
    # Original envelope keys are preserved alongside the normalized ones.
    assert normalized["patentFileWrapperDataBag"] == raw["patentFileWrapperDataBag"]


def test_normalize_empty_databag_yields_empty_results():
    """A missing/empty data bag normalizes to an empty result list and zero hits."""
    normalized = USPTOClient._normalize_search_response(
        {"totalNumFound": 0, "patentFileWrapperDataBag": []}
    )

    assert normalized["results"] == []
    assert normalized["totalHits"] == 0


def test_normalize_total_falls_back_to_page_length_when_total_absent():
    """If neither totalNumFound nor count is present, fall back to the page length."""
    raw = {
        "patentFileWrapperDataBag": [
            {"applicationNumberText": "1"},
            {"applicationNumberText": "2"},
        ]
    }

    normalized = USPTOClient._normalize_search_response(raw)

    assert normalized["results"] == raw["patentFileWrapperDataBag"]
    assert normalized["totalHits"] == 2


def test_normalize_does_not_override_existing_contract_keys():
    """Pre-existing results/totalHits values are left untouched."""
    raw = {
        "patentFileWrapperDataBag": [{"applicationNumberText": "1"}],
        "results": [{"applicationNumberText": "already-normalized"}],
        "totalHits": 42,
    }

    normalized = USPTOClient._normalize_search_response(raw)

    assert normalized["results"] == [{"applicationNumberText": "already-normalized"}]
    assert normalized["totalHits"] == 42


def test_normalize_passes_through_non_search_payloads():
    """Payloads without the search data bag are returned unchanged."""
    raw = {"someOtherKey": "value"}

    assert USPTOClient._normalize_search_response(raw) is raw


def test_year_range_filters_on_filing_date(monkeypatch):
    """start_year/end_year are documented as the *filing* year, so the range
    filter must target filingDate — not grantDate, which returned the wrong
    patents and dropped every ungranted application."""
    captured = {}
    client = USPTOClient(api_key="test")
    monkeypatch.setattr(
        client, "search_patents", lambda **kw: captured.update(kw) or {"results": [], "totalHits": 0}
    )

    client.search_patents_simple("robot", start_year=2020, end_year=2023)

    range_filters = captured["range_filters"]
    assert range_filters[0]["field"] == "applicationMetaData.filingDate"
    assert range_filters[0]["valueFrom"] == "2020-01-01"
    assert range_filters[0]["valueTo"] == "2023-12-31"


def test_parse_result_coerces_single_inventor_dict():
    """The ODP API may return a lone inventor/applicant as a bare dict instead
    of a list; parsing must not walk dict keys and raise AttributeError."""
    client = USPTOClient(api_key="test")
    result = client._parse_patent_result(
        {
            "applicationMetaData": {
                "inventorBag": {"inventorNameText": "Ada Lovelace"},
                "applicantBag": {"applicantNameText": "Analytical Engines Inc"},
            }
        }
    )

    assert result.inventors == ["Ada Lovelace"]
    assert result.applicants == ["Analytical Engines Inc"]
