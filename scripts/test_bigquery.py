#!/usr/bin/env python3
"""
Test BigQuery Patent Search Integration

Quick test to verify BigQuery patent search is working
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_bigquery_availability():
    """Test if BigQuery is available"""
    print("=" * 60)
    print("Testing BigQuery Patent Search Availability")
    print("=" * 60)

    try:
        from mcp_server.bigquery_search import check_bigquery_available

        status = check_bigquery_available()

        print(f"\nAvailable: {status.get('available')}")

        if status.get("available"):
            print("[OK] BigQuery is ready!")
            print(f"  Message: {status.get('message')}")
            if "us_patents" in status:
                print(f"  US Patents accessible: {status.get('us_patents'):,}")
            return True
        else:
            print("[X] BigQuery not available")
            print(f"  Error: {status.get('error')}")
            if "install_command" in status:
                print(f"  Fix: {status.get('install_command')}")
            return False

    except ImportError as e:
        print(f"[X] Import Error: {e}")
        print("  Install with: pip install google-cloud-bigquery db-dtypes")
        return False
    except Exception as e:
        print(f"[X] Error: {e}")
        return False


def test_keyword_search():
    """Test basic keyword search"""
    print("\n" + "=" * 60)
    print("Testing Keyword Search")
    print("=" * 60)

    try:
        from mcp_server.bigquery_search import BigQueryPatentSearch

        searcher = BigQueryPatentSearch()

        print("\nSearching for 'machine learning' patents...")
        results = searcher.search_by_keywords(query="machine learning", country="US", limit=5)

        print(f"\n[OK] Found {len(results)} results")

        for i, patent in enumerate(results, 1):
            print(f"\n{i}. {patent.get('patent_number')}")
            print(f"   Title: {patent.get('title', 'N/A')[:80]}...")
            print(f"   Date: {patent.get('filing_date', 'N/A')}")

        return True

    except Exception as e:
        print(f"[X] Search failed: {e}")
        return False


def test_patent_details():
    """Test getting patent details"""
    print("\n" + "=" * 60)
    print("Testing Patent Details Retrieval")
    print("=" * 60)

    try:
        from mcp_server.bigquery_search import BigQueryPatentSearch

        searcher = BigQueryPatentSearch()

        # Test with a well-known patent
        patent_number = "US10000000B2"
        print(f"\nGetting details for {patent_number}...")

        result = searcher.get_patent_details(patent_number)

        if result:
            print("[OK] Patent found!")
            print(f"   Title: {result.get('title', 'N/A')[:80]}...")
            print(f"   Filing Date: {result.get('filing_date', 'N/A')}")
            print(f"   Grant Date: {result.get('grant_date', 'N/A')}")
            print(f"   CPC Codes: {len(result.get('cpc_codes', []))} codes")
            abstract = result.get("abstract")
            if abstract:
                print(f"   Abstract: {abstract[:100]}...")
            return True
        else:
            print("[X] Patent not found")
            return False

    except Exception as e:
        print(f"[X] Retrieval failed: {e}")
        return False


def test_cpc_search():
    """Test CPC classification search"""
    print("\n" + "=" * 60)
    print("Testing CPC Classification Search")
    print("=" * 60)

    try:
        from mcp_server.bigquery_search import BigQueryPatentSearch

        searcher = BigQueryPatentSearch()

        cpc_code = "G06F"
        print(f"\nSearching for patents with CPC code {cpc_code}...")

        results = searcher.search_by_cpc(cpc_code=cpc_code, limit=5, country="US")

        print(f"\n[OK] Found {len(results)} results")

        for i, patent in enumerate(results, 1):
            print(f"\n{i}. {patent.get('patent_number')}")
            print(f"   Title: {patent.get('title', 'N/A')[:80]}...")

        return True

    except Exception as e:
        print(f"[X] CPC search failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("BigQuery Patent Search Integration Test")
    print("=" * 60)

    tests = [
        ("Availability Check", test_bigquery_availability),
        ("Keyword Search", test_keyword_search),
        ("Patent Details", test_patent_details),
        ("CPC Search", test_cpc_search),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n[X] Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "[OK] PASS" if passed else "[X] FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n All tests passed! BigQuery integration is working.")
        return 0
    elif passed_count > 0:
        print("\n[WARNING] Some tests passed. Check configuration.")
        return 1
    else:
        print("\n[X] All tests failed. Check installation and credentials.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
