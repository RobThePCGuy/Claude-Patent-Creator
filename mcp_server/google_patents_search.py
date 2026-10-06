"""
Google Patents full-text search through SerpApi's Google Patents API.

Why this exists: the BigQuery publications table is unpartitioned, so every
keyword search there reads the full title, abstract and claims text of all
~173M patents (~341 GiB, about $2, three searches per free monthly TiB).
Google Patents searches the same worldwide full text (claims and description
included) and SerpApi returns its results for one search credit each: 250 free
searches a month, then a few cents a search.

Google Patents itself offers no search API and its robots.txt disallows
automated search pages, so the tool goes through SerpApi rather than calling
patents.google.com directly.

Setup: create a free account at https://serpapi.com, then set SERPAPI_API_KEY
(in the project .env or the patent-creator config).

Behavior verified live (2026-10-06):
- Space-separated words must all match (AND); "double quotes" match a phrase.
- Matching covers the full text: patents were found by words that appear only
  in their claims (not their title or abstract).
- Google groups results by patent family unless dups=language is sent, which
  can show a foreign family member instead of the US patent; this module sends
  it so each publication is listed on its own.
- Field operators such as CL= are not reliably accepted through SerpApi, so
  this module does not offer claims-only matching.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

ENDPOINT = "https://serpapi.com/search.json"
SIGNUP_URL = "https://serpapi.com/users/sign_up"
KEY_URL = "https://serpapi.com/manage-api-key"
MAX_PER_PAGE = 100  # SerpApi accepts num between 10 and 100
MIN_PER_PAGE = 10


class GooglePatentsNotConfiguredError(ValueError):
    """SERPAPI_API_KEY is not set."""


class GooglePatentsQuotaError(ValueError):
    """The SerpApi account has no searches left this month."""


def _date_bound(year: int, end: bool) -> str:
    return f"{year:04d}{'1231' if end else '0101'}"


class GooglePatentsSearch:
    """Keyword search over Google Patents' worldwide full text via SerpApi."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 90.0):
        self.api_key = (api_key or os.getenv("SERPAPI_API_KEY") or "").strip()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _redact(self, text: str) -> str:
        return text.replace(self.api_key, "***") if self.api_key else text

    def _get_json(self, url: str) -> dict[str, Any]:
        """GET a SerpApi URL and return its JSON body.

        Every failure is raised as RuntimeError with the key redacted and the
        original exception chain dropped: urllib errors carry the request URL,
        and the URL carries api_key. An HTTP error is never returned as data,
        so an outage cannot read as "no matching patents"."""
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                message = json.load(e).get("error")
            except Exception:
                message = None
            if message:
                return {"error": message, "http_status": e.code}
            raise RuntimeError(f"Google Patents search failed: HTTP {e.code}") from None
        except json.JSONDecodeError:
            raise RuntimeError("Google Patents search returned an unreadable response") from None
        except Exception as e:
            raise RuntimeError(
                f"Google Patents search failed: {self._redact(f'{type(e).__name__}: {e}')}"
            ) from None

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode({**params, "api_key": self.api_key})
        return self._get_json(f"{ENDPOINT}?{query}")

    def account(self) -> dict[str, Any]:
        """Plan and remaining searches. Does not use a search credit."""
        if not self.is_configured():
            raise GooglePatentsNotConfiguredError(self.setup_message())
        query = urllib.parse.urlencode({"api_key": self.api_key})
        data = self._get_json(f"https://serpapi.com/account.json?{query}")
        if data.get("error"):
            raise RuntimeError(f"Google Patents account check failed: {self._redact(data['error'])}")
        return {
            "plan": data.get("plan_name"),
            "searches_per_month": data.get("searches_per_month"),
            "searches_left": data.get("plan_searches_left", data.get("total_searches_left")),
            "used_this_month": data.get("this_month_usage"),
        }

    @staticmethod
    def setup_message() -> str:
        return (
            "Google Patents search needs a free SerpApi key (250 searches a month). "
            f"Sign up at {SIGNUP_URL}, copy the key from {KEY_URL}, and set "
            "SERPAPI_API_KEY in the project .env file."
        )

    def search(
        self,
        query: str,
        country: Optional[str] = None,
        limit: int = 20,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Search Google Patents full text (title, abstract, claims, description).

        Args:
            query: Keywords; all must match. Use "double quotes" for phrases.
            country: Two-letter code to restrict results (e.g. "US"), or None
                for worldwide.
            limit: Results to return, 1-100 (one search credit either way).
            start_year / end_year: Filing-year bounds, inclusive.

        Returns:
            One dict per publication, best match first.

        Raises:
            GooglePatentsNotConfiguredError: no API key.
            GooglePatentsQuotaError: no searches left this month.
            RuntimeError: any other search failure.
        """
        if not self.is_configured():
            raise GooglePatentsNotConfiguredError(self.setup_message())

        params: dict[str, Any] = {
            "engine": "google_patents",
            "q": query,
            "num": max(MIN_PER_PAGE, min(limit, MAX_PER_PAGE)),
            "dups": "language",  # one row per publication, not per family
        }
        if country:
            params["country"] = country.upper()
        if start_year:
            params["after"] = f"filing:{_date_bound(start_year, end=False)}"
        if end_year:
            params["before"] = f"filing:{_date_bound(end_year, end=True)}"

        data = self._request(params)
        error = self._redact(data.get("error") or "")
        if error:
            lowered = error.lower()
            if "hasn't returned any results" in lowered:
                return []
            if "run out of searches" in lowered:
                raise GooglePatentsQuotaError(
                    f"{error} The free plan resets monthly; see {KEY_URL}."
                )
            if "invalid api key" in lowered:
                raise GooglePatentsNotConfiguredError(f"{error} {self.setup_message()}")
            raise RuntimeError(f"Google Patents search failed: {error}")

        results = []
        for r in data.get("organic_results", [])[:limit]:
            number = r.get("publication_number") or ""
            results.append(
                {
                    "patent_number": number,
                    "title": (r.get("title") or "").strip(),
                    # A matching passage, not the full abstract; fetch details
                    # (claims, abstract) with get_patent_bigquery or EPO tools.
                    "snippet": (r.get("snippet") or "").strip(),
                    "country": number[:2],
                    "priority_date": r.get("priority_date"),
                    "filing_date": r.get("filing_date"),
                    "grant_date": r.get("grant_date"),
                    "publication_date": r.get("publication_date"),
                    "assignee": r.get("assignee"),
                    "inventor": r.get("inventor"),
                    "language": r.get("language"),
                    "link": r.get("patent_link"),
                    "pdf": r.get("pdf"),
                }
            )
        return results
