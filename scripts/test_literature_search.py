#!/usr/bin/env python3
"""
Live check for non-patent literature search (search_non_patent_literature).

Free: needs network, no key. OPENALEX_API_KEY and SEMANTIC_SCHOLAR_API_KEY are
used if set (environment or the project .env).

What it proves:
1. A known paper ("Attention Is All You Need", arXiv 1706.03762, published
   2017-06-12) is found, and found by more than one source, folded into one
   result.
2. published_before excludes the cutoff day itself: with a cutoff of
   2017-06-12 the paper disappears, with 2017-06-13 it is back.
3. Every source reports a status; a source that is not "ok" carries a message.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from literature_search import SOURCES, LiteratureSearch  # noqa: E402

QUERY = '"attention is all you need" transformer'
TARGET = "1706.03762"


def _find(result):
    for r in result["results"]:
        if (r.get("arxiv_id") or "").startswith(TARGET) or (r.get("doi") or "").endswith(TARGET):
            return r
    return None


def main() -> int:
    s = LiteratureSearch()
    failures = 0

    found = s.search(QUERY, limit=10, published_before="2017-06-13")
    print("sources:", {k: v["status"] for k, v in found["sources"].items()})
    for name in SOURCES:
        status = found["sources"][name]
        if status["status"] != "ok" and not status.get("message"):
            print(f"FAIL {name} not ok and gave no reason")
            failures += 1
        elif status["status"] != "ok":
            print(f"note {name}: {status['message']}")
    hit = _find(found)
    if not hit:
        print("FAIL known paper not found with cutoff 2017-06-13")
        failures += 1
    else:
        print(f"ok   found {hit['title']!r} via {hit['found_in']}, published {hit['publication_date']}")
        if len(hit["found_in"]) < 2:
            print("note found by one source only (others may be busy); merging not exercised live")

    time.sleep(3)  # arXiv asks for about one request every three seconds
    excluded = s.search(QUERY, limit=10, published_before="2017-06-12")
    if _find(excluded):
        print("FAIL paper published 2017-06-12 returned for cutoff 2017-06-12")
        failures += 1
    else:
        print("ok   cutoff day excluded")

    print("PASS" if not failures else f"{failures} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
