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


# --- Crossref cross-check of listed dates -------------------------------------
# crossref_dates.json was recorded live on 2026-11-09 (full records trimmed to
# their date fields). Three of its DOIs carry wrong dates: a 2026 paper listed
# as 2016-03-16 (DOI registered 2026-04-23), a 2022 Springer chapter listed as
# 2012-02-24 (print 2022), and a 2021 article dated 1970-01-01 (journal issue
# 2021-12-07). The Nature and 1999 Elsevier papers are correctly dated.


def _openalex_work(title, doi, published):
    return {"id": f"https://openalex.org/W{abs(hash(doi))}", "doi": f"https://doi.org/{doi}",
            "title": title, "publication_date": published, "publication_year": int(published[:4])}


def _crossref():
    return (FIX / "crossref_dates.json").read_text(encoding="utf-8")


def test_crossref_parse_reads_registration_and_publisher_dates():
    found = ls.parse_crossref_dates(_crossref())
    assert found["10.66108/mna.v5i01.90"]["registered"].isoformat() == "2026-04-23"
    assert ("print", ls.date(2022, 1, 1)) in found["10.1007/978-3-031-04122-8_16"]["dates"]
    with pytest.raises(ls.SourceError):
        ls.parse_crossref_dates(json.dumps({"status": "error", "message": "bad filter"}))


def _search_with(monkeypatch, works, crossref, cutoff):
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({
        "openalex": json.dumps({"meta": {"count": len(works)}, "results": works}),
        "crossref": crossref,
    }))
    return ls.LiteratureSearch().search("q", sources=["openalex"], published_before=cutoff)


def test_misdated_papers_are_flagged_and_true_dates_are_not(monkeypatch):
    out = _search_with(monkeypatch, [
        _openalex_work("Sign language recognition with MediaPipe", "10.66108/mna.v5i01.90", "2016-03-16"),
        _openalex_work("Synthesizing dynamic time-series data under shock", "10.1007/978-3-031-04122-8_16",
                       "2012-02-24"),
        _openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27"),
        _openalex_work("A 2021 article with an epoch date", "10.32332/ejipd.v7i2.2613", "1970-01-01"),
        _openalex_work("Fuel cell electrodes", "10.1016/s0378-7753(98)00161-x", "1999-01-01"),
    ], _crossref(), "2017-06-12")
    by_doi = {r["doi"]: r for r in out["results"]}
    assert "registered on 2026-04-23" in by_doi["10.66108/mna.v5i01.90"]["date_check"]
    assert "registered on 2022-07-04" in by_doi["10.1007/978-3-031-04122-8_16"]["date_check"]
    assert "date_check" not in by_doi["10.1038/nature14539"]
    assert "1970-01-01" in by_doi["10.32332/ejipd.v7i2.2613"]["date_check"]
    assert "journal issue" in by_doi["10.32332/ejipd.v7i2.2613"]["date_check"]
    assert "date_check" not in by_doi["10.1016/s0378-7753(98)00161-x"]
    assert out["date_cross_check"] == {"status": "ok", "checked": 5, "unchecked": 0}


def test_crossref_down_still_returns_results_and_says_dates_are_unchecked(monkeypatch):
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       ls.SourceError("failed", "crossref search failed: HTTP 503"), "2017-06-12")
    assert out["results"] and out["date_cross_check"]["status"] == "failed"
    assert "could not be cross-checked" in out["note"]
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       KeyError("unexpected"), "2017-06-12")
    assert out["results"] and out["date_cross_check"]["status"] == "failed"


def test_publisher_date_on_or_after_the_cutoff_is_flagged():
    rec = ls._record(title="t", publication_date="2019-11-20")
    late_print = {"registered": ls.date(2019, 11, 19), "dates": [("print", ls.date(2020, 3, 1))]}
    assert "gives 2020-03-01 (print) as its earliest" in ls.crossref_caution(rec, late_print, "2020-01-15")
    early = {"registered": ls.date(2019, 11, 19), "dates": [("print", ls.date(2019, 12, 1))]}
    assert ls.crossref_caution(rec, early, "2020-01-15") is None
    # Online before the cutoff is public, even when the print issue came after.
    online_first = {"registered": ls.date(2012, 9, 1),
                    "dates": [("print", ls.date(2013, 1, 1)), ("online", ls.date(2012, 9, 4))]}
    assert ls.crossref_caution(ls._record(title="t", publication_date="2012-09-04"), online_first, "2013-01-01") is None


def test_late_doi_for_a_paper_older_than_dois_is_not_suspicious():
    # Recorded live: Elsevier 10.1016/s0378-7753(98)00161-x, published 1999-01-01, DOI registered 2002.
    old = {"registered": ls.date(2002, 3, 1), "dates": [("print", ls.date(1999, 1, 1))]}
    assert ls.crossref_caution(ls._record(title="t", publication_date="1999-01-01"), old, "2000-01-01") is None
    # The same lag on a paper listed inside the DOI era is flagged.
    new = {"registered": ls.date(2026, 4, 23), "dates": [("online", ls.date(2016, 3, 16))]}
    assert "registered on 2026-04-23" in ls.crossref_caution(
        ls._record(title="t", publication_date="2016-03-16"), new, "2017-06-12")


def test_dates_crossref_does_not_know_are_labeled_unchecked(monkeypatch):
    out = _search_with(monkeypatch, [
        _openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27"),
        _openalex_work("RAG accuracy", "10.5281/zenodo.8430247", "2023-10-11"),
    ], _crossref(), "2024-01-01")
    by_doi = {r["doi"]: r for r in out["results"]}
    assert by_doi["10.1038/nature14539"]["date_source"].startswith("checked against")
    assert by_doi["10.5281/zenodo.8430247"]["date_source"] == "index only, not cross-checked"
    assert out["date_cross_check"]["unchecked"] == 1
    assert "1 of these dates come from the index alone" in out["note"]


def test_epoch_publisher_date_is_never_trusted_and_issue_date_exposes_it():
    info = {"registered": ls.date(2022, 7, 28),
            "dates": [("online", ls.EPOCH), ("journal issue online", ls.date(2021, 12, 7))]}
    msg = ls.crossref_caution(ls._record(title="t", publication_date="1999-05-01"), info, "2000-01-01")
    assert msg and "2021-12-07" in msg


def test_merged_dates_are_kept_per_source_and_disagreement_is_flagged(monkeypatch):
    work = _openalex_work("Attention is all you need", "10.48550/arxiv.1706.03762", "2016-06-12")
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({
        "openalex": json.dumps({"meta": {"count": 1}, "results": [work]}),
        "arxiv": _arxiv(),
    }))
    out = ls.LiteratureSearch().search("attention", sources=["openalex", "arxiv"], published_before="2018-01-01")
    hit = next(r for r in out["results"] if (r.get("arxiv_id") or "").startswith("1706.03762"))
    assert hit["dates_by_source"]["openalex"] == "2016-06-12"
    assert hit["date_source"] == "index only, not cross-checked", "claimed arXiv's date for OpenAlex's"
    assert "Sources give different dates" in hit["date_check"]


def test_unchecked_count_is_reported_when_crossref_is_down(monkeypatch):
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       ls.SourceError("failed", "crossref search failed: HTTP 503"), "2017-06-12")
    assert out["date_cross_check"]["unchecked"] == 1


def test_publisher_dates_years_apart_are_flagged_even_when_the_earliest_predates_the_cutoff():
    # DOI registered on time, so only the spread between publisher dates can catch it.
    info = {"registered": ls.date(2012, 2, 25),
            "dates": [("online", ls.date(2012, 2, 24)), ("print", ls.date(2022, 1, 1))]}
    msg = ls.crossref_caution(ls._record(title="t", publication_date="2012-02-24"), info, "2014-06-10")
    assert msg and "more than a year apart" in msg


def test_digitized_back_issue_is_not_suspicious():
    # Recorded live: ECS 10.1149/1.2069439, print 1992-05-01, put online 2019-12-07.
    info = {"registered": ls.date(2019, 12, 7),
            "dates": [("print", ls.date(1992, 5, 1)), ("online", ls.date(2019, 12, 7))]}
    assert ls.crossref_caution(ls._record(title="t", publication_date="1992-05-01"), info, "2000-01-01") is None
    shifted = {"registered": ls.date(2022, 9, 1),
               "dates": [("online", ls.date(1969, 12, 31)), ("journal issue online", ls.date(2022, 9, 30))]}
    assert ls.crossref_caution(ls._record(title="t", publication_date="1969-12-31"), shifted, "2000-01-01")
    assert ls.date_caution(ls._record(title="t", publication_date="1969-12-31"), "2000-01-01")


@pytest.mark.parametrize("doi,listed,cutoff,flagged", [
    ("10.21916/mlr.2026.20", "1915-07-01", "2000-01-01", True),       # recorded live
    ("10.58225/tim.2024-2-120-124", "1996-01-01", "2024-06-01", True),  # recorded live
    ("10.58225/tim.2024-2-120-124", "1996-01-01", "2025-01-01", False),  # 2024 is before it: prior art either way
    ("10.1115/imece1998-0845", "1998-11-15", "2000-01-01", False),     # year matches
    ("10.1149/1.2069439", "1992-05-01", "2000-01-01", False),          # digits, not a year
    ("10.1016/0378-7753(94)87014-4", "1994-01-01", "2000-01-01", False),
    ("10.21916/mlr.2026.20", "2025-07-01", "2027-01-01", False),       # listed year is close
])
def test_year_inside_the_doi_exposes_a_wrong_listed_date(doi, listed, cutoff, flagged):
    rec = ls._record(title="t", doi=doi, publication_date=listed)
    assert bool(ls.doi_year_caution(rec, cutoff)) is flagged


def test_late_doi_on_an_old_paper_gets_a_soft_note_not_a_warning():
    rec = ls._record(title="t", publication_date="1905-07-16")
    info = {"registered": ls.date(2026, 6, 4), "dates": [("print", ls.date(1905, 7, 16))]}
    assert ls.crossref_caution(rec, info, "2025-01-01") is None
    assert "usually fine" in ls.crossref_note(rec, info, "2025-01-01")
    assert ls.crossref_note(rec, {"registered": ls.date(2004, 1, 1), "dates": []}, "2025-01-01") is None


def test_search_applies_the_doi_year_check_and_the_soft_note(monkeypatch):
    # Crossref shape as recorded live for 10.2307/jj.43178328.9 (a 2022 chapter listed as 1905).
    crossref = json.dumps({"status": "ok", "message": {"items": [{
        "DOI": "10.2307/jj.43178328.9",
        "created": {"date-time": "2026-06-04T10:00:00Z"},
        "issued": {"date-parts": [[1905, 7, 16]]}, "published-print": {"date-parts": [[1905, 7, 16]]},
    }]}})
    out = _search_with(monkeypatch, [
        _openalex_work("Eating the cost: food prices and the pandemic", "10.21916/mlr.2026.20", "1915-07-01"),
        _openalex_work("El advenimiento (2022)", "10.2307/jj.43178328.9", "1905-07-16"),
    ], crossref, "2025-01-01")
    by_doi = {r["doi"]: r for r in out["results"]}
    assert "contains the year 2026" in by_doi["10.21916/mlr.2026.20"]["date_check"]
    jstor = by_doi["10.2307/jj.43178328.9"]
    assert "date_check" not in jstor and "usually fine" in jstor["date_note"]
