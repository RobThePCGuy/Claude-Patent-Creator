#!/usr/bin/env python3
"""
Test script to verify USPTO Open Data Portal API endpoints

Based on research from:
- https://data.uspto.gov/apis/patent-file-wrapper/search
- US Patent & Trademark Office Microsoft Connector docs
- Stack Exchange API discussions

This script tests various potential endpoint structures to find the working one.
"""

import json
import os
from typing import Any, Optional

import requests


def test_endpoint(
    base_url: str, endpoint: str, api_key: Optional[str], payload: dict[str, Any], description: str
) -> None:
    """Test a specific endpoint configuration"""

    url = f"{base_url}{endpoint}"

    print(f"\n{'='*80}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"{'='*80}")

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Try different header variations
    header_variations = []

    if api_key:
        header_variations = [
            {"x-api-key": api_key},
            {"X-API-KEY": api_key},
            {"USPTO-API-KEY": api_key},
            {"X-Api-Key": api_key},
            {"Api-Key": api_key},
        ]
    else:
        header_variations = [{}]

    for i, auth_headers in enumerate(header_variations):
        test_headers = {**headers, **auth_headers}
        auth_method = list(auth_headers.keys())[0] if auth_headers else "No Auth"

        print(f"\n  Attempt {i+1}: Auth header = {auth_method}")

        try:
            response = requests.post(url, json=payload, headers=test_headers, timeout=10)

            print(f"  [OK] Status Code: {response.status_code}")
            print(f"  [OK] Response Headers: {dict(response.headers)}")

            if response.status_code == 200:
                print("  [OK][OK] SUCCESS! Working endpoint found!")
                try:
                    data = response.json()
                    print(f"  [OK][OK] Response preview: {json.dumps(data, indent=2)[:500]}")
                    return  # Success - stop trying other headers
                except Exception:
                    print(f"  Response Text: {response.text[:500]}")
                return

            elif response.status_code == 401:
                print("  [X] Authentication required")
                try:
                    print(f"  Error: {response.json()}")
                except Exception:
                    print(f"  Text: {response.text[:200]}")

            elif response.status_code == 403:
                print("  [X] Forbidden (wrong API key or unauthorized)")
                try:
                    print(f"  Error: {response.json()}")
                except Exception:
                    print(f"  Text: {response.text[:200]}")

            elif response.status_code == 404:
                print("  [X] Endpoint not found")
                break  # No point trying other headers if endpoint doesn't exist

            elif response.status_code == 400:
                print("  [X] Bad request (wrong payload structure)")
                try:
                    print(f"  Error: {response.json()}")
                except Exception:
                    print(f"  Text: {response.text[:200]}")
                break  # Payload issue, not auth issue

            else:
                print(f"  ? Unexpected status: {response.status_code}")
                print(f"  Text: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print("  [X] Request timed out (10s)")
        except requests.exceptions.ConnectionError as e:
            print(f"  [X] Connection error: {e}")
        except Exception as e:
            print(f"  [X] Error: {e}")


def main():
    """Test various USPTO API endpoint configurations"""

    print("USPTO Open Data Portal API Endpoint Discovery")
    print("=" * 80)

    # Get API key from environment
    api_key = os.getenv("USPTO_API_KEY")
    if api_key:
        print("API Key found")
    else:
        print("[WARNING] No USPTO_API_KEY environment variable found")
        print("   Some endpoints may require authentication")

    # Simple test payload
    simple_payload = {"pagination": {"offset": 0, "limit": 1}}

    # More complete payload
    full_payload = {
        "q": "artificial intelligence",
        "filters": [{"name": "applicationTypeLabelName", "value": ["Utility"]}],
        "pagination": {"offset": 0, "limit": 5},
    }

    # Alternative payload structure (from Microsoft connector docs)
    alt_payload = {"searchText": "artificial intelligence", "start": "0", "rows": "5"}

    # Test configurations based on research
    test_configs = [
        # Configuration 1: From Microsoft connector docs
        (
            "https://data.uspto.gov",
            "/api/v1/applications/search",
            simple_payload,
            "ODP API v1 - Simple payload (minimal test)",
        ),
        # Configuration 2: Full payload
        (
            "https://data.uspto.gov",
            "/api/v1/applications/search",
            full_payload,
            "ODP API v1 - Full payload with filters",
        ),
        # Configuration 3: Alternative endpoint path
        (
            "https://data.uspto.gov",
            "/applications/search",
            simple_payload,
            "ODP API (no version) - Simple payload",
        ),
        # Configuration 4: Patent File Wrapper path
        (
            "https://data.uspto.gov",
            "/apis/patent-file-wrapper/v1/applications/search",
            simple_payload,
            "Patent File Wrapper v1 - Simple payload",
        ),
        # Configuration 5: Bulk data search
        (
            "https://data.uspto.gov",
            "/api/v1/bulk-data/search",
            alt_payload,
            "Bulk Data Search v1 - Alternative payload",
        ),
        # Configuration 6: IBD API (might still work)
        (
            "https://developer.uspto.gov",
            "/ibd-api/v1/patent/application",
            alt_payload,
            "IBD API v1 (legacy) - Alternative payload",
        ),
        # Configuration 7: Direct search endpoint
        (
            "https://data.uspto.gov",
            "/search",
            simple_payload,
            "Direct search endpoint - Simple payload",
        ),
    ]

    # Run tests
    for base_url, endpoint, payload, description in test_configs:
        test_endpoint(base_url, endpoint, api_key, payload, description)

    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
    print("\nSummary:")
    print("- If you see 200 status codes, the endpoint works!")
    print("- If you see 401/403, you need a valid API key")
    print("- If you see 404, that endpoint doesn't exist")
    print("- If you see 400, the payload structure is wrong")
    print("\nTo get an API key:")
    print("1. Visit: https://data.uspto.gov/myodp")
    print("2. Create account (requires ID.me verification)")
    print("3. Generate API key")
    print("4. Set environment variable: export USPTO_API_KEY='your_key'")


if __name__ == "__main__":
    main()
