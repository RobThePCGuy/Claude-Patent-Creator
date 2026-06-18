"""Tests for USPTO ODP client helpers."""

from mcp_server.uspto_api import USPTOClient


def test_normalize_current_odp_search_response():
    """The current ODP search envelope is mapped onto the results/totalHits contract."""
    raw = {
        "count": 1,
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

    assert normalized["totalHits"] == 1
    assert normalized["results"] == raw["patentFileWrapperDataBag"]
    # Original envelope keys are preserved alongside the normalized ones.
    assert normalized["patentFileWrapperDataBag"] == raw["patentFileWrapperDataBag"]


def test_normalize_empty_databag_yields_empty_results():
    """A missing/empty data bag normalizes to an empty result list and zero hits."""
    normalized = USPTOClient._normalize_search_response(
        {"count": 0, "patentFileWrapperDataBag": []}
    )

    assert normalized["results"] == []
    assert normalized["totalHits"] == 0


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
