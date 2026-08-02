#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from mcp_server.bigquery_search import BigQueryPatentSearch

    print("Creating BigQueryPatentSearch instance...")
    searcher = BigQueryPatentSearch()

    print("Checking availability...")
    status = searcher.check_availability()

    print("\nStatus:")
    # Named fields only — status["project"] flows from the ADC credentials
    # file and code scanning flags echoing it.
    print(f"  available: {status.get('available')}")
    for field in ("message", "error", "install_command", "total_rows"):
        if field in status:
            print(f"  {field}: {status[field]}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
