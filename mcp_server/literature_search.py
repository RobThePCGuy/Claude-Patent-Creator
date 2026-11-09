"""
Non-patent literature search over free scholarly sources: OpenAlex, arXiv and
Semantic Scholar.

Why this exists: printed publications are prior art, and examiners cite
journal articles and preprints next to patents. Every other search tool in
this server covers patents only. All three sources here are free and work
without an account, so a prior-art search can include papers at no cost.

Sources and their limits, observed live (2026-11-09):
- OpenAlex (api.openalex.org): ~250M scholarly works (journals, conferences,
  preprints including arXiv, PubMed). Works without a key on a small daily
  allowance (its headers reported 1,000 credits a day, 10 per search, so about
  100 searches). A free key from https://openalex.org/settings/api-key raises
  that. A wrong key is refused (HTTP 401), it does not fall back to keyless.
- arXiv (export.arXiv.org/api): preprints in physics, math, CS, engineering,
  biology and more, often the earliest public version of a result. No key.
  arXiv asks clients to stay at about one request every three seconds; one
  search here is one request.
- Semantic Scholar (api.semanticscholar.org): ~200M papers. Its keyless pool is
  shared by everyone and answered HTTP 429 to the first keyless request in
  testing, so it is tried once and reported as busy when it refuses. A free key
  from https://www.semanticscholar.org/product/api#api-key-form makes it
  reliable.

A source that fails is reported in the result as failed, with the reason. An
empty result list is only "no matches" when every source answered.

Dates come from the indexes and are sometimes wrong (seen live: a paper
published in 2026 listed as 2016). When a cutoff is set, every result with a
DOI is cross-checked in one request against Crossref (api.crossref.org, free,
no key), which records the day the DOI was registered. A DOI registered after
the cutoff and long after the listed date, or a publisher date on or after the
cutoff, puts a date_check on the result.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Optional

from defusedxml import ElementTree as DefusedET

USER_AGENT = "Claude-Patent-Creator (+https://github.com/RobThePCGuy/Claude-Patent-Creator)"
OPENALEX_URL = "https://api.openalex.org/works"
ARXIV_URL = "https://export.arxiv.org/api/query"
S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_URL = "https://api.crossref.org/works"
OPENALEX_KEY_URL = "https://openalex.org/settings/api-key"
S2_KEY_URL = "https://www.semanticscholar.org/product/api#api-key-form"
S2_FIELDS = "title,abstract,year,publicationDate,externalIds,url,venue,authors,openAccessPdf,publicationTypes"
ABSTRACT_CHARS = 1200
MAX_AUTHORS = 6
SOURCES = ("openalex", "arxiv", "semantic_scholar")

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^\s?#]+?)(v\d+)?$", re.IGNORECASE)
_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(.+)$", re.IGNORECASE)
_TOKEN_RE = re.compile(r'"([^"]+)"|(\S+)')


class SourceError(RuntimeError):
    """One source failed; the message is safe to show (no key, no URL)."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _day_before(iso: str) -> date:
    return date.fromisoformat(iso) - timedelta(days=1)


def _tokens(query: str) -> list[str]:
    """Split a query into terms, keeping "quoted phrases" together."""
    out = []
    for phrase, word in _TOKEN_RE.findall(query):
        term = (phrase or word).strip()
        if term:
            out.append(term)
    return out


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clip(text: Optional[str]) -> Optional[str]:
    text = _clean(text)
    if not text:
        return None
    return text if len(text) <= ABSTRACT_CHARS else text[: ABSTRACT_CHARS - 1].rstrip() + "…"


def _bare_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.lower() or None


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def openalex_abstract(inverted: Optional[dict[str, list[int]]]) -> Optional[str]:
    """OpenAlex ships abstracts as {word: [positions]}; put the words back in order."""
    if not inverted:
        return None
    slots: dict[int, str] = {}
    for word, positions in inverted.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def _record(**fields: Any) -> dict[str, Any]:
    rec = {
        "title": "",
        "authors": [],
        "publication_date": None,
        "year": None,
        "venue": None,
        "type": None,
        "doi": None,
        "arxiv_id": None,
        "url": None,
        "pdf": None,
        "abstract": None,
    }
    rec.update(fields)
    if rec["year"] is None and rec["publication_date"]:
        head = str(rec["publication_date"])[:4]
        rec["year"] = int(head) if head.isdigit() else None
    return rec


# --------------------------------------------------------------------------
# Parsers (pure: response body in, records out)
# --------------------------------------------------------------------------


def _body_error(source: str, data: Any) -> None:
    """A 200 response that carries an error, or is not the expected shape, is a
    failure, never an empty result."""
    if not isinstance(data, dict):
        raise SourceError("failed", f"{source} returned an unexpected response")
    message = data.get("error") or (data.get("message") if "code" in data else None)
    if message:
        raise SourceError("failed", f"{source} reported an error: {_clean(str(message))}")


def parse_openalex(data: dict[str, Any]) -> tuple[list[dict[str, Any]], Optional[int]]:
    _body_error("OpenAlex", data)
    if not isinstance(data.get("results"), list) or not isinstance(data.get("meta"), dict):
        raise SourceError("failed", "OpenAlex returned an unexpected response")
    results = []
    for w in data.get("results") or []:
        title = _clean(w.get("display_name") or w.get("title"))
        if not title:
            continue
        doi = _bare_doi(w.get("doi"))
        arxiv_id = None
        m = _ARXIV_DOI_RE.match(doi or "")
        if m:
            arxiv_id = m.group(1)
        primary = w.get("primary_location") or {}
        source = primary.get("source") or {}
        best_oa = w.get("best_oa_location") or {}
        results.append(
            _record(
                title=title,
                authors=[
                    _clean((a.get("author") or {}).get("display_name"))
                    for a in (w.get("authorships") or [])[:MAX_AUTHORS]
                    if (a.get("author") or {}).get("display_name")
                ],
                publication_date=w.get("publication_date"),
                year=w.get("publication_year"),
                venue=source.get("display_name"),
                type=w.get("type"),
                doi=doi,
                arxiv_id=arxiv_id,
                url=primary.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else w.get("id")),
                pdf=best_oa.get("pdf_url") or (w.get("open_access") or {}).get("oa_url"),
                abstract=_clip(openalex_abstract(w.get("abstract_inverted_index"))),
            )
        )
    total = (data.get("meta") or {}).get("count")
    return results, total


def parse_arxiv(xml_text: str) -> tuple[list[dict[str, Any]], Optional[int]]:
    root = DefusedET.fromstring(xml_text)
    if root.tag != f"{_ATOM}feed" or root.find(f"{_OPENSEARCH}totalResults") is None:
        # An outage page or proxy error can come back as HTTP 200.
        raise SourceError("failed", "arXiv returned something other than search results")
    results = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = _clean(entry.findtext(f"{_ATOM}title"))
        entry_id = _clean(entry.findtext(f"{_ATOM}id"))
        if "/api/errors" in entry_id:
            # arXiv reports a bad query as one entry with an errors id and the
            # reason in its summary. That is a failed search, not zero papers.
            reason = _clean(entry.findtext(f"{_ATOM}summary")) or "query rejected"
            raise SourceError("failed", f"arXiv rejected the query: {reason}")
        m = _ARXIV_ID_RE.search(entry_id)
        if not title or not m:
            continue
        arxiv_id = m.group(1)
        pdf = None
        for link in entry.findall(f"{_ATOM}link"):
            if link.get("title") == "pdf":
                pdf = link.get("href")
        published = (entry.findtext(f"{_ATOM}published") or "")[:10] or None
        doi = _bare_doi(entry.findtext(f"{_ARXIV_NS}doi"))
        category = entry.find(f"{_ARXIV_NS}primary_category")
        results.append(
            _record(
                title=title,
                authors=[
                    _clean(a.findtext(f"{_ATOM}name"))
                    for a in entry.findall(f"{_ATOM}author")[:MAX_AUTHORS]
                ],
                publication_date=published,
                venue=_clean(entry.findtext(f"{_ARXIV_NS}journal_ref"))
                or (f"arXiv ({category.get('term')})" if category is not None else "arXiv"),
                type="preprint",
                doi=doi,
                arxiv_id=arxiv_id,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf=pdf,
                abstract=_clip(entry.findtext(f"{_ATOM}summary")),
            )
        )
    total_text = root.findtext(f"{_OPENSEARCH}totalResults")
    total = int(total_text) if total_text and total_text.strip().isdigit() else None
    return results, total


def parse_semantic_scholar(data: dict[str, Any]) -> tuple[list[dict[str, Any]], Optional[int]]:
    _body_error("Semantic Scholar", data)
    if "total" not in data or (data.get("data") is not None and not isinstance(data.get("data"), list)):
        # A search answer always carries "total"; {} or {"message": ...} is a failure.
        msg = _clean(str(data.get("message") or ""))
        raise SourceError("failed", "Semantic Scholar returned no search results" + (f": {msg}" if msg else ""))
    results = []
    for p in data.get("data") or []:
        title = _clean(p.get("title"))
        if not title:
            continue
        ids = p.get("externalIds") or {}
        doi = _bare_doi(ids.get("DOI"))
        arxiv_id = ids.get("ArXiv")
        if not arxiv_id:
            m = _ARXIV_DOI_RE.match(doi or "")
            arxiv_id = m.group(1) if m else None
        types = p.get("publicationTypes") or []
        results.append(
            _record(
                title=title,
                authors=[
                    _clean(a.get("name"))
                    for a in (p.get("authors") or [])[:MAX_AUTHORS]
                    if a.get("name")
                ],
                publication_date=p.get("publicationDate"),
                year=p.get("year"),
                venue=p.get("venue") or None,
                type=types[0] if types else None,
                doi=doi,
                arxiv_id=arxiv_id,
                url=p.get("url"),
                pdf=(p.get("openAccessPdf") or {}).get("url") or None,
                abstract=_clip(p.get("abstract")),
            )
        )
    return results, data.get("total")


MESSAGE_CHARS = 300
MIN_TITLE_KEY = 20  # shorter titles ("Introduction", "Editorial") are too common to match on


def _same_paper(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Title match only counts when nothing else disagrees: two records with
    different DOIs, different arXiv ids, or years more than one apart are
    different papers even if their titles match."""
    both_arxiv = bool(a.get("arxiv_id") and b.get("arxiv_id"))
    if both_arxiv and _strip_version(a["arxiv_id"]) != _strip_version(b["arxiv_id"]):
        return False
    # An arXiv DOI and a journal DOI can be the same work; a shared arXiv id decides.
    if a.get("doi") and b.get("doi") and a["doi"] != b["doi"] and not both_arxiv:
        return False
    far_apart = a.get("year") and b.get("year") and abs(int(a["year"]) - int(b["year"])) > 1
    if far_apart:
        return False
    # Same title, same year, but no author in common: two different papers.
    surnames_a, surnames_b = _surnames(a.get("authors")), _surnames(b.get("authors"))
    return not (surnames_a and surnames_b and not surnames_a & surnames_b)


def _surnames(authors: Optional[list[str]]) -> set[str]:
    """First initial plus surname ("a smith"), so Alice Smith and A. Smith
    match but Alice Smith and Bob Smith do not."""
    out = set()
    for name in authors or []:
        parts = re.sub(r"[^\w\s-]", " ", name.lower()).split()
        if parts:
            out.add(f"{parts[0][0]} {parts[-1]}")
    return out


def _strip_version(arxiv_id: str) -> str:
    return re.sub(r"v[0-9]+$", "", arxiv_id)


DATE_MARGIN_DAYS = 7  # placeholder heuristic: arXiv posts within days of submission
EPOCH = date(1970, 1, 1)  # Unix time zero: what a missing date becomes (seen live on 2020-2021 papers)
# The same zero shifted by a time zone west of UTC (seen live: 1969-12-31 on a 2022 article).
EPOCH_DATES = frozenset({EPOCH, date(1969, 12, 31)})


def date_caution(rec: dict[str, Any], published_before: str) -> Optional[str]:
    """Say when a result's date cannot settle whether it predates the cutoff.

    The sources filter on the dates they hold, but for prior art what counts
    is when the paper became public. Three cases are flagged:
    - only a year is known (Semantic Scholar files these under 1 January),
    - the date is 1 January of the cutoff year (often a year-only placeholder),
    - the date falls within DATE_MARGIN_DAYS of the cutoff (arXiv dates are
      submission dates; the paper is posted after that)."""
    cutoff = date.fromisoformat(published_before)
    raw = rec.get("publication_date")
    if not raw:
        if rec.get("year") and int(rec["year"]) >= cutoff.year:
            return f"Only the year ({rec['year']}) is known; confirm it was public before {published_before}."
        return None
    try:
        when = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return f"Publication date {raw!r} is unclear; confirm it was public before {published_before}."
    if when in EPOCH_DATES:
        return (f"Dated {when.isoformat()}, the date software shows when the real date is missing; "
                f"confirm the real date is before {published_before}.")
    if when.month == 1 and when.day == 1 and when.year == cutoff.year:
        return (f"Dated {when.isoformat()}, which is often a placeholder for 'sometime in {when.year}'; "
                f"confirm it was public before {published_before}.")
    if (cutoff - when).days <= DATE_MARGIN_DAYS:
        return (f"Dated {when.isoformat()}, within {DATE_MARGIN_DAYS} days of the cutoff. Sources record "
                "submission or issue dates; confirm when it actually became public.")
    return None


# placeholder heuristic: the DOIs checked live (Nature, ACM, Springer) were
# registered within a day of publication; a DOI registered more than a year
# after the listed date says the listed date needs checking.
DOI_LAG_DAYS = 365
# Crossref began registering DOIs in 2000, so a paper from before then could
# only get its DOI later; for those a late registration is no evidence at all.
DOI_ERA_START = date(2000, 1, 1)
_CROSSREF_DATES = (("print", "published-print"), ("online", "published-online"), ("issued", "issued"))


def _date_parts(field: Any) -> Optional[date]:
    """Crossref date-parts ([[y]], [[y, m]] or [[y, m, d]]) as the earliest day they allow."""
    try:
        parts = (field or {}).get("date-parts") or []
        nums = [int(x) for x in parts[0] if x is not None][:3]
        if not nums:
            return None
        return date(nums[0], *(nums[1:] + [1, 1])[:2])
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def parse_crossref_dates(body: str) -> dict[str, dict[str, Any]]:
    """Crossref /works?filter=doi:... -> {doi: {"registered": date, "dates": [(label, date)]}}."""
    data = json.loads(body)
    message = data.get("message") if isinstance(data, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise SourceError("failed", "Crossref returned an unexpected response")
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        doi = _bare_doi(it.get("DOI"))
        if not doi:
            continue
        created = (it.get("created") or {}).get("date-time") or ""
        try:
            registered = date.fromisoformat(created[:10]) if created else None
        except ValueError:
            registered = None
        dates = [(label, d) for label, key in _CROSSREF_DATES if (d := _date_parts(it.get(key)))]
        issue = it.get("journal-issue") if isinstance(it.get("journal-issue"), dict) else {}
        dates += [(f"journal issue {label}", d) for label, key in _CROSSREF_DATES[:2]
                  if (d := _date_parts(issue.get(key)))]
        out[doi] = {"registered": registered, "dates": dates}
    return out


def crossref_caution(rec: dict[str, Any], info: dict[str, Any], published_before: str) -> Optional[str]:
    """Say when the publisher's DOI record disagrees with a result's listed date.

    Two signals, both observed live on misdated papers:
    - the DOI was registered after the cutoff and long after the listed date,
      for a listed date in the DOI era (older papers get DOIs late normally);
    - the publisher's earliest date (print, online or issued) is on or after
      the cutoff. The earliest one counts: a paper online before the cutoff
      is public even if its print issue came later;
    - publisher dates (including the journal issue's) more than a year apart
      with the later one on or after the cutoff (seen live: an article dated
      1970-01-01 in a 2021 journal issue), unless the earliest is a print date:
      print first and online later is a digitized back issue.
    1970-01-01 (or 1969-12-31) is never trusted as a publisher date."""
    cutoff = date.fromisoformat(published_before)
    try:
        listed = date.fromisoformat(str(rec.get("publication_date") or "")[:10])
    except ValueError:
        listed = None
    registered = info.get("registered")
    if (listed and registered and listed >= DOI_ERA_START and registered >= cutoff
            and (registered - listed).days > DOI_LAG_DAYS):
        return (f"Listed as published {listed.isoformat()}, but its DOI was only registered on "
                f"{registered.isoformat()}, after your cutoff. Listed dates are sometimes wrong; "
                f"check the publisher's page before relying on it as prior art.")
    dates = [d for d in (info.get("dates") or []) if d[1] not in EPOCH_DATES]
    if dates:
        first_label, first = min(dates, key=lambda d: d[1])
        last_label, last = max(dates, key=lambda d: d[1])
        # Print first and online years later is a digitized back issue (seen
        # live: ECS put 1990s journals online in 2019); the print date stands.
        printed_first = first_label in ("print", "journal issue print")
        if not printed_first and last >= cutoff and (last - first).days > DOI_LAG_DAYS:
            return (f"The publisher's DOI record gives dates more than a year apart ({first_label} "
                    f"{first.isoformat()}, {last_label} {last.isoformat()}), the later one on or after "
                    "your cutoff; confirm when it first became public.")
        label, when = first_label, first
        if when >= cutoff:
            return (f"The publisher's DOI record gives {when.isoformat()} ({label}) as its earliest "
                    f"date, on or after your cutoff; confirm when it first became public.")
    return None


_DOI_YEAR_RE = re.compile(r"(?<![0-9])(19[0-9]{2}|20[0-9]{2})(?![0-9])")


def doi_year_caution(rec: dict[str, Any], published_before: str) -> Optional[str]:
    """Many DOIs carry their publication year (10.21916/mlr.2026.20). A year in
    the DOI later than the listed date and not before the cutoff year means the
    listed date is likely wrong (seen live: that DOI listed as 1915-07-01)."""
    doi, raw = rec.get("doi") or "", str(rec.get("publication_date") or "")
    suffix = doi.split("/", 1)[-1]
    years = [int(y) for y in _DOI_YEAR_RE.findall(suffix)]
    try:
        listed = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    cutoff = date.fromisoformat(published_before)
    if years and max(years) > listed.year + 1 and max(years) >= cutoff.year:
        return (f"Its DOI contains the year {max(years)}, long after its listed date of "
                f"{listed.isoformat()}; listed dates are sometimes wrong, confirm it was public "
                f"before {published_before}.")
    return None


def crossref_note(rec: dict[str, Any], info: dict[str, Any], published_before: str) -> Optional[str]:
    """A softer remark for a paper listed before DOIs existed whose DOI was
    registered after the cutoff: usually a digitized back issue, sometimes a
    wrong date the publisher's own record repeats (seen live: a 2022 chapter
    listed as 1905, DOI registered 2026)."""
    cutoff = date.fromisoformat(published_before)
    try:
        listed = date.fromisoformat(str(rec.get("publication_date") or "")[:10])
    except ValueError:
        return None
    registered = info.get("registered")
    if (registered and listed < DOI_ERA_START and registered >= cutoff
            and (registered - listed).days > DOI_LAG_DAYS):
        return (f"Its DOI was registered on {registered.isoformat()}, after your cutoff. Older papers "
                "often get DOIs late, so this is usually fine; if this paper matters, confirm its date.")
    return None


def sources_disagree(rec: dict[str, Any]) -> Optional[str]:
    """Say when the sources that found a paper give dates far apart."""
    known = {}
    for name, raw in (rec.get("dates_by_source") or {}).items():
        try:
            known[name] = date.fromisoformat(str(raw or "")[:10])
        except ValueError:
            continue
    if len(known) < 2 or (max(known.values()) - min(known.values())).days <= DATE_MARGIN_DAYS:
        return None
    listed = ", ".join(f"{n} {d.isoformat()}" for n, d in sorted(known.items(), key=lambda kv: kv[1]))
    return f"Sources give different dates ({listed}); the earliest public one counts, confirm it."


def merge_results(
    per_source: dict[str, list[dict[str, Any]]], limit: int
) -> list[dict[str, Any]]:
    """Interleave sources in rank order and fold duplicates together.

    Each source's own relevance order is kept: result 1 of every source comes
    before result 2 of any source. Two records are the same paper when they
    share a DOI, an arXiv id, or a normalized title. The first record wins and
    later copies only fill its empty fields and add their source name."""
    merged: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    depth = max((len(v) for v in per_source.values()), default=0)
    for i in range(depth):
        for name in SOURCES:
            rows = per_source.get(name) or []
            if i >= len(rows):
                continue
            rec = rows[i]
            title_key = _title_key(rec["title"])
            id_keys = [
                k
                for k in (
                    f"doi:{rec['doi']}" if rec.get("doi") else None,
                    f"arxiv:{_strip_version(rec['arxiv_id'])}" if rec.get("arxiv_id") else None,
                )
                if k
            ]
            existing = next((index[k] for k in id_keys if k in index), None)
            if existing is None and len(title_key) >= MIN_TITLE_KEY:
                candidate = index.get(f"title:{title_key}")
                if candidate is not None and _same_paper(candidate, rec):
                    existing = candidate
            keys = id_keys + ([f"title:{title_key}"] if len(title_key) >= MIN_TITLE_KEY else [])
            if existing is None:
                existing = {**rec, "found_in": [name], "dates_by_source": {name: rec.get("publication_date")}}
                merged.append(existing)
            else:
                for field, value in rec.items():
                    if existing.get(field) in (None, "", []) and value not in (None, "", []):
                        existing[field] = value
                if name not in existing["found_in"]:
                    existing["found_in"].append(name)
                existing["dates_by_source"].setdefault(name, rec.get("publication_date"))
            for k in keys:
                index.setdefault(k, existing)
    return merged[:limit]


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


class LiteratureSearch:
    """Search free scholarly indexes for non-patent prior art."""

    def __init__(
        self,
        openalex_key: Optional[str] = None,
        semantic_scholar_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.openalex_key = (openalex_key or os.getenv("OPENALEX_API_KEY") or "").strip()
        self.s2_key = (semantic_scholar_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
        self.timeout = timeout

    # -- transport -------------------------------------------------------

    def _redact(self, text: str) -> str:
        for key in (self.openalex_key, self.s2_key):
            if not key:
                continue
            # Error text can carry the key raw, URL-encoded (it rides in the
            # OpenAlex query string) or repr-escaped (header validation errors).
            forms = {key, urllib.parse.quote(key, safe=""), urllib.parse.quote_plus(key),
                     repr(key)[1:-1], repr(key.encode("utf-8"))[2:-1]}
            for form in sorted(forms, key=len, reverse=True):
                if form:
                    text = text.replace(form, "***")
        return text

    def _get(self, source: str, url: str, headers: Optional[dict[str, str]] = None) -> str:
        """GET a URL and return the body. Every failure becomes SourceError with
        no key and no exception chain (urllib errors carry the URL, and the
        OpenAlex URL carries the key)."""
        error: Optional[SourceError] = None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            error = self._http_error(source, e.code)
            if source == "arxiv" and e.code == 400:
                # arXiv explains a rejected query in an Atom error entry.
                try:
                    parse_arxiv(e.read(65536).decode("utf-8", "replace"))
                except SourceError as reason:
                    error = SourceError("failed", str(reason))
                except Exception:
                    pass
        except Exception as e:
            error = SourceError(
                "failed", f"{source} could not be reached: {self._redact(f'{type(e).__name__}: {e}')}"
            )
        # Raised outside the except block so the original exception (which can
        # hold the key in its URL or headers) is not kept as __context__.
        raise error

    def _http_error(self, source: str, code: int) -> SourceError:
        if source == "openalex":
            if code in (401, 403):
                return SourceError(
                    "key_rejected",
                    "OpenAlex refused OPENALEX_API_KEY. Fix or remove the key "
                    f"(keyless search still works), or get a new one at {OPENALEX_KEY_URL}.",
                )
            if code == 429:
                return SourceError(
                    "rate_limited",
                    "OpenAlex's free daily allowance is used up. It resets daily; a free "
                    f"key from {OPENALEX_KEY_URL} raises it (set OPENALEX_API_KEY).",
                )
        if source == "semantic_scholar":
            if code in (401, 403):
                return SourceError(
                    "key_rejected",
                    f"Semantic Scholar refused SEMANTIC_SCHOLAR_API_KEY. Check the key at {S2_KEY_URL}.",
                )
            if code == 429:
                if self.s2_key:
                    return SourceError(
                        "rate_limited",
                        "Semantic Scholar asked to slow down (about one search a second with a key). Try again shortly.",
                    )
                return SourceError(
                    "rate_limited",
                    "Semantic Scholar's shared keyless pool is busy. A free key from "
                    f"{S2_KEY_URL} (set SEMANTIC_SCHOLAR_API_KEY) makes it reliable.",
                )
        if source == "arxiv" and code in (429, 503):
            return SourceError("rate_limited", "arXiv asked to slow down. Wait a few seconds and search again.")
        return SourceError("failed", f"{source} search failed: HTTP {code}")

    def _parse(self, label: str, parser, body: str):
        """Run a parser; any failure becomes a SourceError raised outside the
        except block, so no original exception (which can hold the raw body)
        rides along as __context__."""
        error: Optional[SourceError] = None
        try:
            return parser(body)
        except SourceError as e:
            error = SourceError(e.status, self._redact(str(e)))
        except Exception:
            error = SourceError("failed", f"{label} returned an unreadable response")
        raise error

    # -- per-source searches --------------------------------------------

    def _openalex(self, query, limit, before, after):
        params = {"search": query, "per-page": limit}
        filters = []
        if after:
            filters.append(f"from_publication_date:{after}")
        if before:
            filters.append(f"to_publication_date:{_day_before(before).isoformat()}")
        if filters:
            params["filter"] = ",".join(filters)
        if self.openalex_key:
            params["api_key"] = self.openalex_key
        body = self._get("openalex", f"{OPENALEX_URL}?{urllib.parse.urlencode(params)}")
        return self._parse("OpenAlex", lambda b: parse_openalex(json.loads(b)), body)

    def _arxiv(self, query, limit, before, after):
        terms = []
        for t in _tokens(query):
            # Strip arXiv syntax characters and fold every kind of whitespace to
            # one space, so a phrase stays one quoted term and no operator leaks.
            t = re.sub(r"\s+", " ", re.sub(r'[()":\[\]]', " ", t)).strip()
            if t:
                terms.append(f'all:"{t}"' if " " in t else f"all:{t}")
        if not terms:
            raise SourceError("skipped", "arXiv was not searched: the query has no searchable words.")
        q = " AND ".join(terms)
        if before or after:
            lo = date.fromisoformat(after).strftime("%Y%m%d") if after else "19910101"
            hi = _day_before(before).strftime("%Y%m%d") if before else "29991231"
            q += f" AND submittedDate:[{lo}0000 TO {hi}2359]"
        params = {"search_query": q, "start": 0, "max_results": limit}
        body = self._get("arxiv", f"{ARXIV_URL}?{urllib.parse.urlencode(params)}")
        return self._parse("arXiv", parse_arxiv, body)

    def _semantic_scholar(self, query, limit, before, after):
        params = {"query": query, "limit": limit, "fields": S2_FIELDS}
        if before or after:
            lo = after or ""
            hi = _day_before(before).isoformat() if before else ""
            params["publicationDateOrYear"] = f"{lo}:{hi}"
        headers = {"x-api-key": self.s2_key} if self.s2_key else None
        body = self._get("semantic_scholar", f"{S2_URL}?{urllib.parse.urlencode(params)}", headers)
        return self._parse("Semantic Scholar", lambda b: parse_semantic_scholar(json.loads(b)), body)

    # -- public ---------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 20,
        published_before: Optional[str] = None,
        published_after: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Search every chosen source at once and merge the answers.

        Args:
            query: Keywords; "double quotes" keep a phrase together.
            limit: Papers to return after merging (each source is asked for this many).
            published_before: ISO date. Only papers published before this day
                (use the invention's priority date).
            published_after: ISO date. Only papers published on or after this day.
            sources: Subset of SOURCES; default all three.

        Returns:
            {"results": [...], "sources": {name: {"status", ...}}, "note": str}
            A source that failed has status other than "ok" and a "message".
            With published_before, also "date_cross_check": {"status",
            "checked", "unchecked", ...}, the Crossref check of the results'
            dates; each result gets "date_source", and "date_check" (confirm
            before citing) or "date_note" (usually fine) when its date is in doubt.
        """
        chosen = [s for s in (sources or SOURCES) if s in SOURCES]
        runners = {
            "openalex": self._openalex,
            "arxiv": self._arxiv,
            "semantic_scholar": self._semantic_scholar,
        }
        per_source: dict[str, list[dict[str, Any]]] = {}
        report: dict[str, dict[str, Any]] = {}

        with ThreadPoolExecutor(max_workers=len(chosen) or 1) as pool:
            futures = {
                name: pool.submit(runners[name], query, limit, published_before, published_after)
                for name in chosen
            }
            for name, fut in futures.items():
                try:
                    rows, total = fut.result()
                    per_source[name] = rows
                    report[name] = {"status": "ok", "returned": len(rows), "total_matches": total}
                except SourceError as e:
                    # Redact first, then shorten, so a cut can never leave part of a key.
                    report[name] = {"status": e.status, "message": self._redact(str(e))[:MESSAGE_CHARS]}
                except Exception as e:  # never let one source sink the others
                    report[name] = {
                        "status": "failed",
                        "message": self._redact(f"{name} failed: {type(e).__name__}: {e}"),
                    }

        results = merge_results(per_source, limit)
        cross_check: Optional[dict[str, Any]] = None
        if published_before and results:
            publisher, cross_check = self._crossref_dates(results)
            for r in results:
                cautions = [date_caution(r, published_before), sources_disagree(r),
                            doi_year_caution(r, published_before)]
                info = publisher.get(r.get("doi") or "")
                if info:
                    r["date_source"] = "checked against the publisher's DOI record (Crossref)"
                    cautions.append(crossref_caution(r, info, published_before))
                    note_text = crossref_note(r, info, published_before)
                    if note_text and not any(cautions):
                        r["date_note"] = note_text
                elif (r.get("dates_by_source") or {}).get("arxiv") and \
                        str(r["dates_by_source"]["arxiv"])[:10] == str(r.get("publication_date") or "")[:10]:
                    r["date_source"] = "arXiv submission date"
                else:
                    r["date_source"] = "index only, not cross-checked"
                cautions = [c for c in cautions if c]
                if cautions:
                    r["date_check"] = " ".join(cautions)
        answered = [n for n in chosen if report[n]["status"] == "ok"]
        missing = [n for n in chosen if report[n]["status"] != "ok"]

        if not answered:
            note = (
                "No source could be searched, so this says nothing about prior art. "
                "See each source's message."
            )
        elif not results:
            note = (
                f"No papers matched in {', '.join(answered)}. That is not proof that no "
                "prior art exists: try synonyms, fewer terms, or broader wording."
            )
        else:
            note = f"{len(results)} papers, best matches first. Searched: {', '.join(answered)}."
        if missing and answered:
            note += f" Not searched this time: {', '.join(missing)} (see sources)."
        if cross_check:
            unchecked = sum(r.get("date_source") == "index only, not cross-checked" for r in results)
            cross_check["unchecked"] = unchecked
            if cross_check["status"] != "ok":
                note += (" Publication dates could not be cross-checked with Crossref this time; "
                         "confirm each date on the publisher's page before citing.")
            elif unchecked:
                note += (f" {unchecked} of these dates come from the index alone and could not be "
                         "cross-checked (see date_source); confirm them before citing.")
            flagged = sum("date_check" in r for r in results)
            noted = sum("date_note" in r for r in results)
            if flagged:
                note += f" {flagged} carry a date_check: confirm those dates before citing them as prior art."
            if noted:
                note += (f" {noted} older papers got their DOIs after your cutoff (date_note), "
                         "which is normal for digitized back issues.")

        out = {"results": results, "sources": report, "note": note}
        if cross_check:
            out["date_cross_check"] = cross_check
        return out

    def _crossref_dates(self, results: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """One Crossref request for every result's DOI. Never fails the search:
        a failure is reported and the note tells the user to check dates by hand."""
        dois = sorted({r["doi"] for r in results
                       if r.get("doi") and "," not in r["doi"] and not _ARXIV_DOI_RE.match(r["doi"])})
        if not dois:
            return {}, {"status": "ok", "checked": 0}
        # No "select": Crossref will not select journal-issue, which carries
        # the issue date that exposes 1970-01-01 article dates. Full records
        # for 31 DOIs measured 115 KB, 0.7 s.
        params = {"filter": ",".join(f"doi:{d}" for d in dois), "rows": len(dois)}
        try:
            body = self._get("crossref", f"{CROSSREF_URL}?{urllib.parse.urlencode(params)}")
            found = self._parse("Crossref", parse_crossref_dates, body)
        except SourceError as e:
            return {}, {"status": e.status, "message": self._redact(str(e))[:MESSAGE_CHARS]}
        except Exception as e:  # the cross-check never sinks the search
            return {}, {"status": "failed", "message": self._redact(f"Crossref failed: {type(e).__name__}")}
        return found, {"status": "ok", "checked": len(found)}
