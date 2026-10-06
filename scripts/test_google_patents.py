#!/usr/bin/env python3
"""
Live check for Google Patents full-text search (search_patents_google).

Uses 3 search credits (free plan: 250 a month). Needs SERPAPI_API_KEY in the
environment or the project .env.

What it proves:
1. The key works and shows searches left (free; no credit used).
2. A patent is found by words that appear in its claims but not in its title
   or abstract, i.e. matching really covers claim text.
3. Country and filing-year filters restrict results.
4. A CPC group term (CPC=G10L17/00) restricts results to that class.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from google_patents_search import GooglePatentsSearch  # noqa: E402

# US10000000B2 ("Coherent LADAR using intra-pixel quadrature detection"):
# "serializing", "oscillating" and "amplifying" appear in its claims and not
# in its title or abstract (checked against its Google Patents page).
CLAIMS_TARGET = "US10000000B2"
CLAIMS_QUERY = "ladar serializing oscillating amplifying"


def main() -> int:
    g = GooglePatentsSearch()
    if not g.is_configured():
        print(f"[X] {GooglePatentsSearch.setup_message()}")
        return 1

    ok = True
    account = g.account()
    print(f"[OK] Key works: {account['plan']}, {account['searches_left']} searches left")

    results = g.search(CLAIMS_QUERY, country="US", limit=20)
    numbers = [r["patent_number"] for r in results]
    if CLAIMS_TARGET in numbers:
        print(f"[OK] Claims-text match: {CLAIMS_TARGET} found at #{numbers.index(CLAIMS_TARGET) + 1}")
    else:
        print(f"[X] Claims-text match: {CLAIMS_TARGET} not in top 20 for {CLAIMS_QUERY!r}")
        ok = False
    if any(r["country"] != "US" for r in results):
        print("[X] country='US' returned non-US results")
        ok = False

    dated = g.search(CLAIMS_QUERY, start_year=2015, end_year=2015, limit=20)
    years = {(r["filing_date"] or "")[:4] for r in dated}
    if dated and years == {"2015"}:
        print(f"[OK] Filing-year filter: {len(dated)} results, all filed 2015")
    else:
        print(f"[X] Filing-year filter returned filing years {sorted(years)}")
        ok = False

    cpc = g.search("speaker verification CPC=G10L17/00", country="US", limit=10)
    if cpc:
        # Confirm on the patent's own page (an allowed path) that it carries the class.
        import urllib.request

        req = urllib.request.Request(cpc[0]["link"], headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        if "G10L17/" in page:
            print(f"[OK] CPC filter: {cpc[0]['patent_number']} is classified in G10L17")
        else:
            print(f"[X] CPC filter: {cpc[0]['patent_number']} page shows no G10L17 class")
            ok = False
    else:
        print("[X] CPC filter returned nothing")
        ok = False

    print("\nAll checks passed." if ok else "\nSome checks failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
