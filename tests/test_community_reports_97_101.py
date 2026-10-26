"""Regression tests for community reports #97-#101.

All hermetic: mocked BigQuery client, fixture OPS responses, tmp dirs.
No credentials, network, or paid queries.
"""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from mcp_server import diagram_generator
from mcp_server.bigquery_search import (
    BigQueryConfigError,
    BigQueryPatentSearch,
)
from mcp_server.epo_api import EPOClient
from mcp_server.tools.diagram_tools import register_diagram_tools

GIB = 1024**3
KEY = "PATENT_BIGQUERY_MAX_BYTES_BILLED"


@pytest.fixture(autouse=True)
def _hermetic_config(monkeypatch, tmp_path):
    monkeypatch.delenv(KEY, raising=False)
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))


def _searcher(dry_estimate=1, rows=()):
    searcher = object.__new__(BigQueryPatentSearch)
    client = MagicMock()
    job = client.query.return_value
    job.total_bytes_processed = dry_estimate
    job.result.return_value = iter(list(rows))
    searcher.client = client
    return searcher


# --- #97: family_id is a STRING column -------------------------------------


def test_family_search_binds_family_id_as_string():
    searcher = _searcher()

    searcher.search_patent_family(55456961, limit=5)

    # Every client.query call (dry run + real) must bind a STRING family_id.
    assert searcher.client.query.call_count == 2
    for call in searcher.client.query.call_args_list:
        params = {p.name: p for p in call.kwargs["job_config"].query_parameters}
        assert params["family_id"].type_ == "STRING"
        assert params["family_id"].value == "55456961"
        assert params["limit"].type_ == "INT64"


# --- #101: invalid explicit caps fail closed -------------------------------


@pytest.mark.parametrize(
    "value", ["1048576", "1", "0", "-5", f"{GIB - 1}", "abc", "1.5e9", " "]
)
def test_invalid_env_cap_raises_before_any_query(monkeypatch, value):
    monkeypatch.setenv(KEY, value)
    searcher = _searcher()

    with pytest.raises(BigQueryConfigError) as exc:
        searcher.search_patent_family(55456961)

    assert KEY in str(exc.value)
    assert "no query was run" in str(exc.value)
    searcher.client.query.assert_not_called()  # dry run included


@pytest.mark.parametrize("value", ["1048576", "0", "-1", "nope"])
def test_invalid_config_file_cap_raises(tmp_path, value):
    (tmp_path / "config.json").write_text(f'{{"{KEY}": "{value}"}}')
    searcher = _searcher()

    with pytest.raises(BigQueryConfigError):
        searcher._resolve_max_bytes_billed()
    with pytest.raises(BigQueryConfigError):
        searcher._assert_within_budget("SELECT 1", [])
    searcher.client.query.assert_not_called()


def test_env_overrides_valid_config_file_and_still_fails_closed(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text(f'{{"{KEY}": "{2 * GIB}"}}')
    monkeypatch.setenv(KEY, "1048576")

    with pytest.raises(BigQueryConfigError):
        _searcher()._resolve_max_bytes_billed()


@pytest.mark.parametrize("value", [str(GIB), str(5 * GIB), str(400 * GIB)])
def test_valid_env_cap_used_exactly(monkeypatch, value):
    monkeypatch.setenv(KEY, value)
    searcher = _searcher()

    assert searcher._resolve_max_bytes_billed() == int(value)
    searcher.search_patent_family(1)
    real_call = searcher.client.query.call_args_list[-1]
    assert real_call.kwargs["job_config"].maximum_bytes_billed == int(value)


def test_absent_or_empty_cap_uses_default(monkeypatch):
    assert _searcher()._resolve_max_bytes_billed() == BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED
    monkeypatch.setenv(KEY, "")
    assert _searcher()._resolve_max_bytes_billed() == BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED


@pytest.mark.parametrize("value", ["1048576", "0", "-3", "junk"])
def test_env_only_fallback_without_config_module(monkeypatch, value):
    import mcp_server.bigquery_search as bq

    monkeypatch.setattr(bq, "_config", None)
    monkeypatch.setenv(KEY, value)
    searcher = _searcher()

    with pytest.raises(BigQueryConfigError):
        searcher._assert_within_budget("SELECT 1", [])
    searcher.client.query.assert_not_called()


def test_env_only_fallback_valid_and_absent(monkeypatch):
    import mcp_server.bigquery_search as bq

    monkeypatch.setattr(bq, "_config", None)
    assert _searcher()._resolve_max_bytes_billed() == BigQueryPatentSearch.DEFAULT_MAX_BYTES_BILLED
    monkeypatch.setenv(KEY, str(3 * GIB))
    assert _searcher()._resolve_max_bytes_billed() == 3 * GIB


def test_invalid_cap_is_visible_to_mcp_tool_caller(monkeypatch):
    from mcp_server import bigquery_search
    from mcp_server.tools.bigquery_tools import register_bigquery_tools

    searcher = _searcher()
    monkeypatch.setenv(KEY, "1048576")
    monkeypatch.setitem(sys.modules, "bigquery_search", bigquery_search)
    monkeypatch.setattr(bigquery_search, "BigQueryPatentSearch", lambda: searcher)
    tools = {}

    class FakeMCP:
        def tool(self):
            def register(fn):
                tools[fn.__name__] = fn
                return fn
            return register

    def noop(*args, **kwargs):
        pass

    register_bigquery_tools(FakeMCP(), noop, noop, noop, noop, None, None, None,
                            lambda name: (lambda fn: fn))
    result = asyncio.run(tools["search_patent_family_bigquery"](55456961))
    assert "PATENT_BIGQUERY_MAX_BYTES_BILLED" in result[0]["error"]
    assert "no query was run" in result[0]["error"]
    searcher.client.query.assert_not_called()


# --- #99: multi-hit OPS search responses ------------------------------------


def _exchange_doc(country, number, kind, title):
    return {
        "@country": country,
        "@doc-number": number,
        "@kind": kind,
        "bibliographic-data": {
            "invention-title": {"@lang": "en", "$": title},
        },
    }


def _search_response(exchange_documents):
    return {
        "ops:world-patent-data": {
            "ops:biblio-search": {
                "@total-result-count": "6486",
                "ops:search-result": {"exchange-documents": exchange_documents},
            }
        }
    }


@pytest.fixture
def epo():
    return EPOClient(key="k", secret="s")


def test_search_parses_multiple_wrappers(epo):
    resp = _search_response(
        [
            {"exchange-document": _exchange_doc("EP", "1000001", "A1", "Water filter")},
            {"exchange-document": _exchange_doc("US", "2000002", "B2", "Filter jug")},
        ]
    )

    results = epo._parse_search_results(resp)

    assert [r["publication_number"] for r in results] == ["EP1000001", "US2000002"]
    assert results[1]["country"] == "US"


def test_search_parses_single_wrapper(epo):
    resp = _search_response(
        {"exchange-document": _exchange_doc("EP", "1000001", "A1", "Water filter")}
    )

    results = epo._parse_search_results(resp)

    assert [r["publication_number"] for r in results] == ["EP1000001"]


# --- #100: family members prefer docdb ids ----------------------------------


def _member(docdb, epodoc, order=("docdb", "epodoc")):
    ids = {
        "docdb": {"@document-id-type": "docdb", **docdb},
        "epodoc": {"@document-id-type": "epodoc", **epodoc},
    }
    return {
        "@family-id": "19012345",
        "publication-reference": {"document-id": [ids[o] for o in order]},
    }


@pytest.mark.parametrize("order", [("docdb", "epodoc"), ("epodoc", "docdb")])
def test_family_members_use_docdb_fields(epo, order):
    resp = {
        "ops:world-patent-data": {
            "ops:patent-family": {
                "ops:family-member": [
                    _member(
                        {"country": "EP", "doc-number": "1000000", "kind": "A1", "date": "20000517"},
                        {"doc-number": "EP1000000", "date": "20000517"},
                        order,
                    ),
                    _member(
                        {"country": {"$": "US"}, "doc-number": {"$": "6093011"},
                         "kind": {"$": "A"}, "date": {"$": "20000725"}},
                        {"doc-number": {"$": "US6093011"}, "date": {"$": "20000725"}},
                        order,
                    ),
                ]
            }
        }
    }

    members = epo._parse_family_response(resp)

    assert [(m["publication_number"], m["country"], m["kind_code"]) for m in members] == [
        ("EP1000000", "EP", "A1"),
        ("US6093011", "US", "A"),
    ]
    assert members[1]["publication_date"] == "20000725"


def test_family_single_member_epodoc_only_still_parses(epo):
    resp = {
        "ops:world-patent-data": {
            "ops:patent-family": {
                "ops:family-member": {
                    "publication-reference": {
                        "document-id": {"@document-id-type": "epodoc", "doc-number": "EP1000000"}
                    }
                }
            }
        }
    }

    members = epo._parse_family_response(resp)

    assert members[0]["doc_number"] == "EP1000000"


# --- #98: add_diagram_references on create_* default output -----------------


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg"><g>'
    '<text x="0" y="0">Housing</text></g></svg>'
)


@pytest.fixture
def diagram_tools(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    # Keep the generator's data-dir default out of the real home directory.
    data_diagrams = tmp_path / "data" / "diagrams"
    monkeypatch.setattr(
        diagram_generator.PatentDiagramGenerator.__init__, "__defaults__", (data_diagrams,)
    )
    monkeypatch.setitem(sys.modules, "diagram_generator", diagram_generator)

    tools = {}

    class FakeMCP:
        def tool(self):
            def deco(fn):
                tools[fn.__name__] = fn
                return fn
            return deco

    noop = lambda *a, **k: None  # noqa: E731
    register_diagram_tools(
        FakeMCP(), noop, noop, noop, noop, object, lambda name: (lambda fn: fn)
    )
    return tools, project, tmp_path


def test_add_references_accepts_cwd_diagrams_output(diagram_tools):
    tools, project, _ = diagram_tools
    svg = project / "diagrams" / "block.svg"
    svg.parent.mkdir()
    svg.write_text(SVG)

    result = tools["add_diagram_references"](str(svg), {"Housing": 10})

    assert result["success"], result
    out = project / "diagrams" / "block_annotated.svg"
    assert result["path"] == str(out)
    assert "Housing (10)" in out.read_text()


def test_add_references_relative_path_in_nested_cwd_dir(diagram_tools):
    tools, project, _ = diagram_tools
    svg = project / "figs" / "fig1.svg"
    svg.parent.mkdir()
    svg.write_text(SVG)

    result = tools["add_diagram_references"]("figs/fig1.svg", {"Housing": 10})

    assert result["success"], result


def test_add_references_still_rejects_traversal(diagram_tools):
    tools, _, tmp = diagram_tools
    outside = tmp / "outside.svg"
    outside.write_text(SVG)

    result = tools["add_diagram_references"]("../outside.svg", {"Housing": 10})

    assert not result["success"]
    assert "inside the project directory" in result["error"]
    assert not (tmp / "outside_annotated.svg").exists()


def test_add_references_still_rejects_symlink_escape(diagram_tools):
    tools, project, tmp = diagram_tools
    outside = tmp / "outside.svg"
    outside.write_text(SVG)
    (project / "diagrams").mkdir()
    link = project / "diagrams" / "link.svg"
    link.symlink_to(outside)

    result = tools["add_diagram_references"](str(link), {"Housing": 10})

    assert not result["success"]
    assert "inside the project directory" in result["error"]
    assert not (tmp / "outside_annotated.svg").exists()
