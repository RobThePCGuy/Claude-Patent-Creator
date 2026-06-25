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
