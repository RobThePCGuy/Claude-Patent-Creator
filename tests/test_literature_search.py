"""Non-patent literature search: parsing, merging, and honest failure reporting.

The parser tests read real responses recorded from OpenAlex and arXiv on
2026-11-09 (tests/fixtures/literature/). The live behavior of all three
sources is checked by scripts/test_literature_search.py, which needs network
but no key.
"""

import json
import urllib.error
from pathlib import Path

import pytest

from mcp_server import literature_search as ls
from mcp_server.validation import SearchLiteratureInput, validate_input

FIX = Path(__file__).parent / "fixtures" / "literature"


def _openalex():
    return json.loads((FIX / "openalex_attention.json").read_text(encoding="utf-8"))


def _arxiv(name="arxiv_attention.xml"):
    return (FIX / name).read_text(encoding="utf-8")


# --- parsers on recorded responses -----------------------------------------


def test_openalex_parse_rebuilds_abstract_and_ids():
    rows, total = ls.parse_openalex(_openalex())
    assert total and total >= len(rows) == 3
    first = rows[0]
    assert first["title"] == "Sequence to Sequence Transduction with Hard Monotonic Attention"
    assert first["publication_date"] == "2017-04-24" and first["year"] == 2017
    assert first["authors"], "authors dropped"
    # The abstract is rebuilt from OpenAlex's inverted index, words in order.
    assert first["abstract"] and first["abstract"].split()[:3] == ["We", "present", "a"]
    assert not any(r["doi"] and r["doi"].startswith("http") for r in rows), "DOI kept its URL prefix"


def test_arxiv_parse_reads_ids_dates_and_pdf():
    rows, total = ls.parse_arxiv(_arxiv())
    assert len(rows) == 2 and total is not None and total >= len(rows)
    titles = [r["title"] for r in rows]
    assert "Attention Is All You Need" in titles
    paper = rows[titles.index("Attention Is All You Need")]
    assert paper["arxiv_id"] == "1706.03762"
    assert paper["publication_date"] == "2017-06-12"
    assert paper["pdf"].startswith("https://arxiv.org/pdf/1706.03762")
    assert paper["type"] == "preprint"


def test_arxiv_parse_empty_feed_is_zero_results():
    rows, total = ls.parse_arxiv(_arxiv("arxiv_empty.xml"))
    assert rows == [] and total == 0


def test_arxiv_parser_refuses_entity_expansion():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE f [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        '<feed xmlns="http://www.w3.org/2005/Atom"><title>&b;</title></feed>'
    )
    from defusedxml import EntitiesForbidden

    with pytest.raises(EntitiesForbidden):
        ls.parse_arxiv(bomb)


def test_semantic_scholar_parse():
    data = {
        "total": 1,
        "data": [
            {
                "title": " Robotic  mower ",
                "abstract": "x" * 2000,
                "year": 2012,
                "publicationDate": None,
                "externalIds": {"DOI": "10.1/ABC"},
                "url": "https://www.semanticscholar.org/paper/1",
                "venue": "",
                "authors": [{"name": "A. Person"}],
                "openAccessPdf": None,
                "publicationTypes": ["JournalArticle"],
            }
        ],
    }
    rows, total = ls.parse_semantic_scholar(data)
    assert total == 1
    r = rows[0]
    assert r["title"] == "Robotic mower" and r["year"] == 2012 and r["doi"] == "10.1/abc"
    assert r["venue"] is None and r["pdf"] is None
    assert len(r["abstract"]) == ls.ABSTRACT_CHARS


# --- merging ---------------------------------------------------------------


def test_merge_folds_the_same_paper_across_sources():
    oa, _ = ls.parse_openalex(_openalex())
    ax, _ = ls.parse_arxiv(_arxiv())
    # OpenAlex lists the arXiv paper under its arXiv DOI.
    oa.append(ls._record(title="Attention is all you need", doi="10.48550/arxiv.1706.03762",
                         arxiv_id="1706.03762", publication_date="2017-06-12"))
    merged = ls.merge_results({"arxiv": ax, "openalex": oa}, limit=50)
    hits = [m for m in merged if ls._title_key(m["title"]) == "attentionisallyouneed"]
    assert len(hits) == 1
    # Rank 0 of openalex and of arxiv are interleaved before this copy, so the
    # arXiv record lands first and the OpenAlex copy folds into it.
    assert hits[0]["found_in"] == ["arxiv", "openalex"]
    assert hits[0]["doi"] == "10.48550/arxiv.1706.03762", "later copy did not fill the empty DOI"


def test_merge_interleaves_by_rank_and_respects_limit():
    a = [ls._record(title=f"A{i}") for i in range(5)]
    b = [ls._record(title=f"B{i}") for i in range(5)]
    merged = ls.merge_results({"openalex": a, "arxiv": b}, limit=4)
    assert [m["title"] for m in merged] == ["A0", "B0", "A1", "B1"]


# --- search(): one failing source never reads as "no prior art" -------------


def _fake_get(responses):
    def _get(self, source, url, headers=None):
        r = responses[source]
        if isinstance(r, Exception):
            raise r
        return r

    return _get


def test_failed_source_is_reported_not_silent(monkeypatch):
    monkeypatch.setattr(
        ls.LiteratureSearch,
        "_get",
        _fake_get({
            "openalex": json.dumps(_openalex()),
            "arxiv": ls.SourceError("failed", "arxiv could not be reached: timeout"),
            "semantic_scholar": ls.SourceError("rate_limited", "busy"),
        }),
    )
    out = ls.LiteratureSearch().search("attention transduction", limit=5)
    assert out["sources"]["openalex"]["status"] == "ok"
    assert out["sources"]["arxiv"]["status"] == "failed"
    assert out["sources"]["semantic_scholar"]["status"] == "rate_limited"
    assert "Not searched this time: arxiv, semantic_scholar" in out["note"]
    assert out["results"]


def test_all_sources_down_says_nothing_about_prior_art(monkeypatch):
    err = ls.SourceError("failed", "down")
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get(dict.fromkeys(ls.SOURCES, err)))
    out = ls.LiteratureSearch().search("anything")
    assert out["results"] == []
    assert out["note"].startswith("No source could be searched")


def test_empty_answer_is_not_called_proof(monkeypatch):
    monkeypatch.setattr(
        ls.LiteratureSearch,
        "_get",
        _fake_get({"openalex": json.dumps({"meta": {"count": 0}, "results": []}),
                   "arxiv": _arxiv("arxiv_empty.xml")}),
    )
    out = ls.LiteratureSearch().search("zzq", sources=["openalex", "arxiv"])
    assert "not proof" in out["note"] and out["results"] == []


def test_http_errors_map_to_actionable_messages_without_the_key(monkeypatch):
    s = ls.LiteratureSearch(openalex_key="SECRET-KEY-123")

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(ls.urllib.request, "urlopen", boom)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert e.value.status == "key_rejected"
    assert "SECRET-KEY-123" not in str(e.value) and e.value.__cause__ is None

    def net(req, timeout):
        raise OSError(f"connection reset for {req.full_url}")

    monkeypatch.setattr(ls.urllib.request, "urlopen", net)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert "SECRET-KEY-123" not in str(e.value)


# --- request building --------------------------------------------------------


def test_published_before_excludes_the_cutoff_day(monkeypatch):
    seen = {}

    def capture(self, source, url, headers=None):
        seen[source] = url
        return {"openalex": json.dumps({"meta": {"count": 0}, "results": []}),
                "arxiv": _arxiv("arxiv_empty.xml"),
                "semantic_scholar": json.dumps({"total": 0, "data": []})}[source]

    monkeypatch.setattr(ls.LiteratureSearch, "_get", capture)
    ls.LiteratureSearch().search('"neural network" mower', published_before="2017-06-13",
                                 published_after="2010-01-01")
    assert "to_publication_date%3A2017-06-12" in seen["openalex"]
    assert "from_publication_date%3A2010-01-01" in seen["openalex"]
    assert "201001010000+TO+201706122359" in seen["arxiv"]
    assert "all%3A%22neural+network%22" in seen["arxiv"], "phrase not kept together for arXiv"
    assert "publicationDateOrYear=2010-01-01%3A2017-06-12" in seen["semantic_scholar"]


def test_input_validation():
    ok = validate_input(SearchLiteratureInput, query=" battery ", published_before="2020-01-01")
    assert ok.query == "battery" and ok.published_before.isoformat() == "2020-01-01"
    for bad in (
        {"query": "   "},
        {"query": "x", "published_before": "2020-13-01"},
        {"query": "x", "published_before": "2010-01-01", "published_after": "2015-01-01"},
        {"query": "x", "sources": ["google"]},
        {"query": "x", "sources": []},
        {"query": "x", "limit": 51},
    ):
        with pytest.raises(ValueError):
            validate_input(SearchLiteratureInput, **bad)


# --- review findings: each one was a way to report a false "nothing found" ----




def test_arxiv_error_feed_is_a_failure_not_zero_results():
    # Recorded from arXiv for search_query=all:(( (served with HTTP 400).
    with pytest.raises(ls.SourceError) as e:
        ls.parse_arxiv(_arxiv("arxiv_error.xml"))
    assert "Invalid query string" in str(e.value)


@pytest.mark.parametrize("body", ["<html><body>Service unavailable</body></html>",
                                  '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'])
def test_arxiv_non_feed_200_is_a_failure(body):
    with pytest.raises(ls.SourceError):
        ls.parse_arxiv(body)


@pytest.mark.parametrize("body", [{}, {"message": "Internal Server Error"}])
def test_semantic_scholar_bodies_without_total_are_failures(body):
    with pytest.raises(ls.SourceError):
        ls.parse_semantic_scholar(body)


def test_key_echoed_in_a_source_error_is_redacted(monkeypatch):
    monkeypatch.setattr(ls.LiteratureSearch, "_get",
                        _fake_get({"openalex": json.dumps({"error": "Invalid api_key REVIEW-KEY-123"})}))
    out = ls.LiteratureSearch(openalex_key="REVIEW-KEY-123").search("x", sources=["openalex"])
    assert out["sources"]["openalex"]["status"] == "failed"
    assert "REVIEW-KEY-123" not in json.dumps(out)
    # Place the key across the cut point: the prefix is
    # "OpenAlex reported an error: " (28 chars), so the key spans 295-309.
    long_echo = json.dumps({"error": "x" * (ls.MESSAGE_CHARS - 28 - 5) + "REVIEW-KEY-123"})
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({"openalex": long_echo}))
    out = ls.LiteratureSearch(openalex_key="REVIEW-KEY-123").search("x", sources=["openalex"])
    assert "REVIE" not in json.dumps(out), "shortened before redacting"


def test_unreadable_body_keeps_no_context(monkeypatch):
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({"openalex": '{"error":"fake+key/123="'}))
    with pytest.raises(ls.SourceError) as e:
        ls.LiteratureSearch(openalex_key="fake+key/123=")._openalex("x", 5, None, None)
    assert e.value.__context__ is None


@pytest.mark.parametrize("body", [{"error": "Query failed"}, {"message": "bad", "code": "400"}, []])
def test_error_bodies_with_http_200_are_failures(body):
    for parse in (ls.parse_openalex, ls.parse_semantic_scholar):
        with pytest.raises(ls.SourceError):
            parse(body)


def test_query_with_no_words_left_for_arxiv_is_skipped_not_searched(monkeypatch):
    def never(self, source, url, headers=None):
        raise AssertionError("no request should be sent")

    monkeypatch.setattr(ls.LiteratureSearch, "_get", never)
    out = ls.LiteratureSearch().search('(): ""', sources=["arxiv"])
    assert out["sources"]["arxiv"]["status"] == "skipped"
    assert out["note"].startswith("No source could be searched")


def test_same_title_different_papers_stay_apart():
    a = ls._record(title="Introduction", doi="10.1000/one", year=2010)
    b = ls._record(title="Introduction", doi="10.1000/two", year=2020, abstract="Bob")
    merged = ls.merge_results({"openalex": [a], "semantic_scholar": [b]}, 10)
    assert len(merged) == 2
    long_a = ls._record(title="A long and specific title about mower wires", doi="10.1/a", year=2010)
    long_b = ls._record(title="A long and specific title about mower wires", doi="10.1/b", year=2010)
    assert len(ls.merge_results({"openalex": [long_a], "arxiv": [long_b]}, 10)) == 2
    same = ls._record(title="A long and specific title about mower wires", year=2011)
    assert len(ls.merge_results({"openalex": [long_a], "arxiv": [same]}, 10)) == 1
    alice = ls._record(title="A review of neural networks", doi="10.1000/alice", year=2017, authors=["Alice Smith"])
    bob = ls._record(title="A review of neural networks", year=2017, authors=["Bob Jones"], abstract="Bob's")
    assert len(ls.merge_results({"openalex": [alice], "semantic_scholar": [bob]}, 10)) == 2
    bob_smith = ls._record(title="A review of neural networks", year=2017, authors=["Bob Smith"])
    assert len(ls.merge_results({"openalex": [alice], "semantic_scholar": [bob_smith]}, 10)) == 2
    alice2 = ls._record(title="A review of neural networks", year=2017, authors=["A. Smith", "C. Lee"])
    assert len(ls.merge_results({"openalex": [alice], "semantic_scholar": [alice2]}, 10)) == 1


@pytest.mark.parametrize(
    "rec,flagged",
    [
        ({"publication_date": None, "year": 2017}, True),     # year only, cutoff year
        ({"publication_date": None, "year": 2015}, False),    # year only, earlier year
        ({"publication_date": "2017-01-01", "year": 2017}, True),  # Jan 1 placeholder
        ({"publication_date": "2017-06-10", "year": 2017}, True),  # days before cutoff
        ({"publication_date": "2016-03-04", "year": 2016}, False),
    ],
)
def test_uncertain_dates_are_flagged(rec, flagged):
    assert bool(ls.date_caution(ls._record(title="t", **rec), "2017-06-13")) is flagged


def test_escaped_and_encoded_keys_are_redacted():
    s = ls.LiteratureSearch(openalex_key="fake+key/123=", semantic_scholar_key="FAKE-SECRET\nbad")
    text = "url api_key=fake%2Bkey%2F123%3D and api_key=fake+key/123= header b'FAKE-SECRET\\nbad'"
    out = s._redact(text)
    assert "FAKE-SECRET" not in out and "%2Bkey" not in out and "key/123" not in out


def test_transport_error_keeps_no_context_holding_the_key(monkeypatch):
    s = ls.LiteratureSearch(openalex_key="SECRET-KEY-123")

    def net(req, timeout):
        raise OSError(f"reset for {req.full_url}")

    monkeypatch.setattr(ls.urllib.request, "urlopen", net)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert e.value.__context__ is None and e.value.__cause__ is None


def test_whitespace_inside_a_phrase_cannot_split_it(monkeypatch):
    seen = {}

    def capture(self, source, url, headers=None):
        seen[source] = url
        return _arxiv("arxiv_empty.xml")

    monkeypatch.setattr(ls.LiteratureSearch, "_get", capture)
    ls.LiteratureSearch().search('"neural\tOR\tnetwork"', sources=["arxiv"])
    assert "all%3A%22neural+OR+network%22" in seen["arxiv"]
