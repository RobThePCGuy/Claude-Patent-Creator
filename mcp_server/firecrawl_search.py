"""
Non-patent literature search through Firecrawl's search API.

Why this exists: printed publications are prior art (35 USC 102(a)(1), EPC
Art. 54(2)), and examiners cite journal articles, preprints and technical
web pages next to patents. Every other search tool here covers patents only
(Google Patents, BigQuery, USPTO, EPO), so this module adds a search over
research papers and the open web.

Setup: create an account at https://www.firecrawl.dev/?utm_source=Claude-Patent-Creator&utm_medium=integration,
then set FIRECRAWL_API_KEY (in the project .env or the patent-creator config).
Without the key the tool returns setup instructions and makes no request.

Search modes:
- research_only=True sends categories=["research"], which searches research
  papers and academic sources (strongest in life sciences, physics and
  computer science). Results arrive as web pages (data.web: url, title,
  description) or as paper records (data.research: primaryId, title,
  abstract); both shapes are parsed.
- research_only=False searches the whole web, the better choice for
  engineering topics, standards, product manuals and technical write-ups.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

ENDPOINT = "https://api.firecrawl.dev/v2/search"
SIGNUP_URL = "https://www.firecrawl.dev/?utm_source=Claude-Patent-Creator&utm_medium=integration"
ORIGIN = "Claude-Patent-Creator"
MAX_RESULTS = 20

_ID_URLS = {
    "arxiv": "https://arxiv.org/abs/{}",
    "doi": "https://doi.org/{}",
    "pmid": "https://pubmed.ncbi.nlm.nih.gov/{}/",
    "pmcid": "https://pmc.ncbi.nlm.nih.gov/articles/{}/",
}


class FirecrawlNotConfiguredError(ValueError):
    """FIRECRAWL_API_KEY is not set or was rejected."""


def _paper_url(primary_id: str) -> Optional[str]:
    namespace, _, value = primary_id.partition(":")
    template = _ID_URLS.get(namespace.strip().lower())
    return template.format(value.strip()) if template and value.strip() else None


class FirecrawlSearch:
    """Search research papers and web pages for non-patent prior art."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 75.0):
        self.api_key = (api_key or os.getenv("FIRECRAWL_API_KEY") or "").strip()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _redact(self, text: str) -> str:
        return text.replace(self.api_key, "***") if self.api_key else text

    @staticmethod
    def setup_message() -> str:
        return (
            "Non-patent literature search needs a Firecrawl API key. "
            f"Create one at {SIGNUP_URL} and set FIRECRAWL_API_KEY in the project .env file."
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the search endpoint and return its JSON body.

        Every failure is raised as RuntimeError with the key redacted and the
        original exception chain dropped. An HTTP error is never returned as
        data, so an outage cannot read as "no matching literature"."""
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                message = json.load(e).get("error")
            except Exception:
                message = None
            detail = f": {self._redact(str(message))}" if message else ""
            if e.code == 401:
                raise FirecrawlNotConfiguredError(
                    f"Firecrawl rejected the API key (HTTP 401){detail}. {self.setup_message()}"
                ) from None
            if e.code == 402:
                raise RuntimeError(
                    f"Firecrawl search failed: the account is out of Firecrawl credits (HTTP 402){detail}"
                ) from None
            if e.code == 429:
                raise RuntimeError(
                    f"Firecrawl search failed: rate limited (HTTP 429){detail}. Retry shortly."
                ) from None
            raise RuntimeError(f"Firecrawl search failed: HTTP {e.code}{detail}") from None
        except json.JSONDecodeError:
            raise RuntimeError("Firecrawl search returned an unreadable response") from None
        except Exception as e:
            raise RuntimeError(
                f"Firecrawl search failed: {self._redact(f'{type(e).__name__}: {e}')}"
            ) from None

    def search(
        self, query: str, limit: int = 10, research_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Search for non-patent literature.

        Args:
            query: Natural-language or keyword query.
            limit: Results to return, 1-20.
            research_only: Restrict to research papers and academic sources;
                False searches the whole web.

        Returns:
            One dict per result (title, url, snippet, source), best match first.

        Raises:
            FirecrawlNotConfiguredError: no API key, or the key was rejected.
            RuntimeError: any other search failure.
        """
        if not self.is_configured():
            raise FirecrawlNotConfiguredError(self.setup_message())

        payload: dict[str, Any] = {
            "query": query,
            "limit": max(1, min(limit, MAX_RESULTS)),
            "origin": ORIGIN,
        }
        if research_only:
            payload["categories"] = ["research"]

        body = self._post_json(payload)
        if body.get("success") is False:
            error = self._redact(str(body.get("error") or "unknown error"))
            raise RuntimeError(f"Firecrawl search failed: {error}")

        data = body.get("data") or {}
        results: list[dict[str, Any]] = []
        for paper in data.get("research") or []:
            primary_id = (paper.get("primaryId") or "").strip()
            results.append(
                {
                    "title": (paper.get("title") or "").strip(),
                    "url": paper.get("url") or _paper_url(primary_id),
                    "snippet": (paper.get("abstract") or "").strip(),
                    "id": primary_id or None,
                    "source": "research_index",
                }
            )
        for page in data.get("web") or []:
            results.append(
                {
                    "title": (page.get("title") or "").strip(),
                    "url": page.get("url"),
                    "snippet": (page.get("description") or "").strip(),
                    "source": page.get("category") or "web",
                }
            )
        return results[:limit]
