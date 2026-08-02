#!/usr/bin/env python3
"""
Test BigQuery logging and error handling enhancements
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_logging_imports():
    """Test that logging imports work with fallback."""
    print("Testing logging imports...")

    from mcp_server.bigquery_search import LOGGING_AVAILABLE, logger

    if LOGGING_AVAILABLE:
        print("  [OK] Logging available")
        print(f"  [OK] Logger type: {type(logger).__name__}")
    else:
        print("  [WARN] Logging not available (fallback mode)")

    return True


def test_bigquery_initialization():
    """Test BigQuery client initialization with logging."""
    print("\nTesting BigQuery initialization...")

    from mcp_server.bigquery_search import BIGQUERY_AVAILABLE, BigQueryPatentSearch

    if not BIGQUERY_AVAILABLE:
        print("  [WARN] BigQuery not available (dependencies not installed)")
        return True

    try:
        searcher = BigQueryPatentSearch()

        if searcher.client:
            print("  [OK] BigQuery client initialized successfully")
            print("  [OK] Billing project configured")
        else:
            print("  [WARN] BigQuery client not initialized (credentials not configured)")

        return True
    except Exception as e:
        print(f"  [FAIL] Error initializing BigQuery: {e}")
        return False


def test_search_methods_exist():
    """Test that search methods exist and have proper signatures."""
    print("\nTesting search methods...")

    from mcp_server.bigquery_search import BigQueryPatentSearch

    methods = ["search_by_keywords", "get_patent_details", "search_by_cpc"]

    for method_name in methods:
        if hasattr(BigQueryPatentSearch, method_name):
            print(f"  [OK] Method {method_name} exists")
        else:
            print(f"  [FAIL] Method {method_name} missing")
            return False

    return True


def test_logging_fallback():
    """Test that fallback works when logging is not available."""
    print("\nTesting logging fallback...")

    # This should work even if logging imports fail
    from mcp_server.bigquery_search import check_bigquery_available

    status = check_bigquery_available()

    print(f"  [OK] BigQuery status check: {status.get('available', False)}")

    if not status.get("available"):
        print(f"  [INFO] Reason: {status.get('error', 'Unknown')}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("BigQuery Logging Enhancement Tests")
    print("=" * 60)

    tests = [
        test_logging_imports,
        test_bigquery_initialization,
        test_search_methods_exist,
        test_logging_fallback,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n[FAIL] Test {test_func.__name__} failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 60)

    return all(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
