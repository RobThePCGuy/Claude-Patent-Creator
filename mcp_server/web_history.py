"""
When a web page was first public, from the Internet Archive's capture index.

A disclosure audit needs the earliest date a product page, demo or repository
was public. Web fetch tools are often refused by web.archive.org, so this asks
the archive's CDX index directly. Free, no key, read-only.

A capture proves the page was public no later than that moment. It does not
prove the page was not public earlier: the archive only saw it when it looked.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CDX_URL = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "Claude-Patent-Creator (+https://github.com/RobThePCGuy/Claude-Patent-Creator)"
MATCH_TYPES = ("exact", "prefix", "host", "domain")


class WebHistoryError(Exception):
    """The archive could not be reached or answered with something unreadable."""


def _normalize(url: str) -> str:
    u = (url or "").strip()
    if not u or any(c.isspace() for c in u):
        raise ValueError("Give one web address without spaces, for example example.com/product.")
    if "://" in u:
        parts = urllib.parse.urlsplit(u)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("Only http and https addresses can be looked up.")
        u = parts.netloc + parts.path + (f"?{parts.query}" if parts.query else "")
    return u.rstrip("/") or u


def _when(ts: str) -> str:
    """20020120142510 -> 2002-01-20T14:25:10Z"""
    ts = (ts + "00000000000000")[:14]
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z"


def _query(params: dict[str, Any], timeout: float, tries: int = 3) -> list[list[str]]:
    url = f"{CDX_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace").strip()
            rows = json.loads(body) if body else []
            return rows[1:] if rows and rows[0] and rows[0][0] == "timestamp" else rows
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 * (attempt + 1))
    raise WebHistoryError(f"The Internet Archive did not answer ({type(last).__name__}: {last}). Try again in a few minutes.")


def web_history(url: str, match: str = "exact", limit: int = 5, timeout: float = 45) -> dict[str, Any]:
    """Earliest and latest archived captures of a page, host or whole domain."""
    if match not in MATCH_TYPES:
        raise ValueError(f"match must be one of {', '.join(MATCH_TYPES)}.")
    limit = max(1, min(int(limit), 25))
    target = _normalize(url)
    base = {
        "url": target,
        "matchType": match,
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200",
        "collapse": "timestamp:8",  # at most one capture per day
    }
    first = _query({**base, "limit": limit}, timeout)
    latest = _query({**base, "limit": -1}, timeout) if first else []

    def row(r: list[str]) -> dict[str, str]:
        return {"captured": _when(r[0]), "url": r[1], "archive_link": f"https://web.archive.org/web/{r[0]}/{r[1]}"}

    out: dict[str, Any] = {"looked_up": target, "match": match, "source": "Internet Archive (web.archive.org CDX index)"}
    if not first:
        out["found"] = False
        out["meaning"] = (
            "The archive has no successful capture. That does not show the page was never public; "
            "the archive may never have visited it. Date it from other evidence."
        )
        return out
    out["found"] = True
    out["first_captures"] = [row(r) for r in first]
    if latest:
        out["latest_capture"] = row(latest[-1])
    out["meaning"] = (
        f"Public no later than {out['first_captures'][0]['captured'][:10]} (the earliest capture). "
        "It may have been public earlier; the archive only records when it visited. "
        "Open the archive link to see what the page showed on that date."
    )
    return out
