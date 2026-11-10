---
name: bigquery-patent-search
description: Fast, cloud-based patent searching across 100 million+ worldwide patents using Google BigQuery - keyword search, CPC classification, patent details retrieval
tools: Bash, Read, Write
model: sonnet
---

# BigQuery Patent Search Skill

> **Windows PowerShell:** replace a macOS/Linux Python invocation with `& "$HOME\patent-creator-venv\Scripts\python.exe"` and a CLI invocation with `& "$HOME\patent-creator-venv\Scripts\patent-creator.exe"`. Keep script paths quoted. Python code blocks are Python source, not shell commands.

Fast, cloud-based patent searching across 100 million+ worldwide patents using Google BigQuery.

## When to Use

Invoke this skill when users ask to:
- Search for prior art patents
- Find patents in a specific technology area
- Search by CPC classification code
- Look up patent details by publication number
- Conduct freedom-to-operate searches
- Research patent landscapes

## What This Skill Does

Provides access to Google's public patent dataset:

1. **Keyword Search** across 100M+ patents:
   - Full-text search of titles, abstracts, claims
   - Filter by country (US, EP, JP, CN, etc.)
   - Filter by filing/grant date ranges
   - Fast cloud-based queries (< 5 seconds)

2. **CPC Classification Search**:
   - Search by CPC code (e.g., "G06F16/", "H04L29/06")
   - Browse patent classifications
   - Find patents in specific technical domains

3. **Patent Details Retrieval**:
   - Get full patent text by publication number
   - Access title, abstract, claims, description
   - View CPC codes, inventors, assignees
   - See filing and grant dates

## Required Setup

This skill requires Google Cloud authentication:

**Prerequisites**:
1. Google Cloud Project (free to create)
2. BigQuery API enabled (queries consume scan quota)
3. Application Default Credentials configured

**Setup Commands**:
```bash
# Install Google Cloud SDK (if not installed)
# Visit: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth application-default login

# Set project (get ID from console.cloud.google.com)
"$HOME/patent-creator-venv/bin/patent-creator" config set GOOGLE_CLOUD_PROJECT your-project-id
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set GOOGLE_CLOUD_PROJECT your-project-id
```

Restart Claude Code after saving the project. BigQuery is optional; the **Patent Search** skill uses SerpApi by default.

## How to Use

When this skill is invoked:

1. **Initialize BigQuery searcher**:
   ```python
   import os
   import sys
   sys.path.insert(0, os.environ.get('CLAUDE_PLUGIN_ROOT', '.'))
   from mcp_server.bigquery_search import BigQueryPatentSearch

   searcher = BigQueryPatentSearch()
   ```

2. **Search by keywords**:
   ```python
   results = searcher.search_by_keywords(
       query="blockchain authentication",
       limit=20,
       country="US",  # Optional: filter by country
       start_year=2020,  # Optional: filter by year
       end_year=2024
   )
   ```

3. **Search by CPC code**:
   ```python
   results = searcher.search_by_cpc(
       cpc_code="G06F16/",  # CPC prefix
       limit=20,
       country="US"
   )
   ```

4. **Get patent details**:
   Description retrieval is opt-in and can scan over 1 TiB, exceeding the default
   350 GiB cap. Use the free dry-run estimate and obtain approval for any cap
   increase before retrying. Omit `include_description` for a smaller lookup.
   ```python
   patent = searcher.get_patent_details(
       patent_number="US10123456B2",  # Publication number
       include_abstract=True,
       include_claims=True,
       include_description=True  # Large scan; opt in only when needed
   )
   ```

## BigQuery Dataset

Uses `patents-public-data.patents` on Google BigQuery:
- **100M+ worldwide patents**
- **12M+ US patents** with full text
- Updated weekly
- Each query consumes scan quota. A default keyword search scans hundreds of GiB.

## Search Result Format

Keyword search returns these keys (unavailable dates are null):
```python
{
    "patent_number": "US-10123456-B2",
    "application_number": "US-201615123456-A",
    "title": "Method and system for...",
    "abstract": "A system for...",
    "filing_date": "2019-01-15",
    "grant_date": "2020-06-30",
    "publication_date": "2020-06-30",
    "country": "US",
    "family_id": "12345678",
    "relevance_score": 4
}
```

Detail lookups return the identifiers, title, dates, country and family ID above,
plus `cpc_codes` and `ipc_codes`, but no `relevance_score`. They include `claims`
by default. `abstract` and `description` require their respective `include_*`
flags. Text sections are strings. Inventors, assignees and priority dates are
not returned by this implementation. Missing requested text may be empty.

## Presentation Format

Present search results as:

```
PATENT SEARCH RESULTS
====================

Query: "blockchain authentication"
Found: 247 patents (showing top 20)
Date Range: 2020-2024
Country: US

[1] US10123456B2 - System for blockchain-based authentication
    Assignee: Example Corp
    Filed: 2019-01-15 | Granted: 2020-06-30
    CPC: G06F16/245, H04L29/06

    Abstract: A system for authenticating users using blockchain
    technology with distributed ledger verification...

[2] US10234567B1 - Method of secure authentication using blockchain
    ...

---

Top 5 Most Relevant:
1. US10123456B2 (95% relevance)
2. US10234567B1 (92% relevance)
...
```

## Advanced Search Techniques

1. **Boolean Operators** in queries:
   - "blockchain AND authentication"
   - "encryption OR cryptography"
   - "(mobile OR wireless) AND security"

2. **Phrase Search** (include the double quotes in the query string):
   - `query='"distributed ledger technology"'`
   - `query='"public key infrastructure"'`

3. **CPC Code Hierarchies**:
   - "G06F" = Computing
   - "G06F16/" = Information retrieval
   - "G06F16/245" = Structured query language

## Common CPC Codes

- **G06F**: Computing, calculating, counting
- **H04L**: Digital communication
- **G06Q**: Business methods
- **H04W**: Wireless communication
- **G06N**: Computer systems based on specific models
- **G06T**: Image processing

## Error Handling

If BigQuery is not configured:
1. Check if `google-cloud-bigquery` is installed
2. Verify authentication: `gcloud auth application-default login`
3. Confirm project ID in environment: `GOOGLE_CLOUD_PROJECT`
4. Test with: `"$HOME/patent-creator-venv/bin/patent-creator" check-bigquery`

## Cost Considerations

BigQuery pricing:
- **First 1 TiB/month**: FREE
- **After 1 TiB**: $6.25 per TiB queried (on-demand)
- **Observed default keyword scan**: roughly 325-341 GiB per search, about three searches per 1 TiB allowance. These are historical measurements; use the dry-run estimate for the current query.
- Selecting fewer text fields reduces scan size. Country, date and keyword filters do not reliably reduce bytes scanned on this unpartitioned table.
- **Bytes-billed ceiling**: enforced per-query via `PATENT_BIGQUERY_MAX_BYTES_BILLED` (default 350 GiB)

## Tools Available

- **Bash**: To run Python BigQuery searches
- **Read**: To load saved search results
- **Write**: To save patent search results
- **Grep**: To search through saved results
