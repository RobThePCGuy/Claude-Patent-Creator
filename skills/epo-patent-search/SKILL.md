---
name: epo-patent-search
description: Search European patents using EPO OPS API (full-text, legal status, families) and BigQuery (100M+ patents, EP filter) for prior art, competitive intelligence, and freedom-to-operate analysis
tools: Bash, Read, Write
model: sonnet
---

# EPO Patent Search Skill

Search European patents using the EPO Open Patent Services (OPS) API and Google BigQuery with EP country filtering.

## When to Use

Invoke this skill when users ask to:
- Search for European patents
- Find EP prior art for a technology
- Check legal status of EP patents
- Explore patent families across jurisdictions
- Conduct EP freedom-to-operate analysis
- Research the EP patent landscape for a technology area
- Get full-text EP claims or descriptions

## What This Skill Does

Provides access to European patent data through two methods:

1. **EPO OPS API** (European Patent Data):
   - Full-text EP patent retrieval (claims, description)
   - Legal status and procedural history
   - INPADOC patent family linking
   - Applicant and inventor search
   - EP publication types (A1, A2, A3, B1, B2)
   - Designated contracting states

2. **BigQuery** (Worldwide Patents, EP Filter):
   - Fast keyword search across 100M+ patents with country="EP"
   - CPC classification search for EP patents
   - Filing trend analysis
   - Cross-jurisdiction comparison

## Required Setup

### BigQuery (Primary)

**Prerequisites**:
1. Google Cloud Project (free to create)
2. BigQuery API enabled
3. Application Default Credentials configured

**Setup**:
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
```

### EPO OPS API (Optional, for full-text/legal status)

**Prerequisites**:
1. Register at https://developers.epo.org/
2. Create an application to get Consumer Key and Secret
3. Set environment variables

**Setup**:
```bash
export EPO_OPS_CONSUMER_KEY=your-key
export EPO_OPS_CONSUMER_SECRET=your-secret
```

## How to Use

When this skill is invoked:

1. **Determine search type**:
   - Keyword search: use BigQuery with country="EP" for speed
   - Full-text retrieval: use EPO OPS for complete claims/description
   - Legal status: use EPO OPS for procedural data
   - Family search: use EPO OPS INPADOC family service
   - CPC search: use BigQuery for broad classification browsing

2. **Execute search**:

   **Full-text keyword search (EP patents)**, falling back to
   `search_patents_bigquery` with the same arguments if not configured:
   ```python
   results = search_patents_google(
       query="blockchain authentication",
       country="EP",
       limit=20,
       start_year=2020
   )
   ```

   **BigQuery CPC search (EP patents)**:
   ```python
   results = search_patents_by_cpc_bigquery(
       cpc_code="H04L9/32",
       country="EP",
       limit=30
   )
   ```

   **EPO OPS full-text retrieval**:
   ```python
   results = search_epo_patents(
       query="EP3456789",
       search_type="full_text"
   )
   ```

   **EPO OPS family search**:
   ```python
   results = search_epo_patents(
       query="EP3456789",
       search_type="family"
   )
   ```

3. **Present results**:
   - Rank by relevance
   - Show key metadata (title, applicant, dates, IPC/CPC)
   - Highlight legal status (in force, expired, opposed)
   - Provide links to Espacenet for full documents
   - Note patent family members in other jurisdictions

## Search Result Format

```python
{
    "publication_number": "EP3456789A1",
    "title": "Authentication system using distributed ledger",
    "abstract": "A system for authenticating...",
    "applicant": "Example GmbH",
    "inventors": ["Hans Mueller", "Maria Schmidt"],
    "filing_date": "2019-03-15",
    "publication_date": "2020-01-22",
    "grant_date": null,
    "ipc_codes": ["H04L9/32", "G06F21/31"],
    "cpc_codes": ["H04L9/32", "G06F21/31"],
    "designated_states": ["DE", "FR", "GB", "NL", "IT"],
    "priority_claims": ["US16/234567 (2018-12-28)"],
    "family_id": "67890123",
    "legal_status": "Examination in progress",
    "publication_type": "A1"
}
```

## EP Publication Types

| Code | Type | Description |
|------|------|-------------|
| A1 | Application + search | Published EP application with search report |
| A2 | Application only | Published without search report |
| A3 | Search report | Search report published separately |
| B1 | Granted patent | Patent specification as granted |
| B2 | Amended patent | Amended specification after opposition |
| B3 | Limited patent | Patent after limitation proceedings |

## Cross-Jurisdiction Linking

Use `family_id` to find related patents across jurisdictions:

```
EP3456789A1 (European application)
├── US10123456B2 (US counterpart)
├── CN112345678A (Chinese counterpart)
├── JP2020-123456A (Japanese counterpart)
└── WO2019/123456A1 (PCT application)
```

This is essential for:
- Prior art analysis (one patent may be available in multiple languages)
- Freedom-to-operate (check where patent is in force)
- Competitive intelligence (track filing strategy)

## Presentation Format

Present search results as:

```
EP PATENT SEARCH RESULTS
=========================

Query: "blockchain authentication"
Source: BigQuery (EP filter) + EPO OPS
Found: 89 EP patents
Date Range: 2020-2025

[1] EP3456789B1 - Authentication system using distributed ledger
    Applicant: Example GmbH (DE)
    Filed: 2019-03-15 | Granted: 2022-08-10
    IPC: H04L9/32, G06F21/31
    Status: Patent in force (validated in DE, FR, GB)
    Family: US10123456B2, CN112345678B, WO2019/123456A1
    Espacenet: https://worldwide.espacenet.com/patent/search?q=EP3456789

[2] EP3567890A1 - Blockchain-based identity verification method
    Applicant: Tech Corp (US)
    Filed: 2020-01-10 | Published: 2021-06-16
    IPC: H04L9/00, G06Q20/38
    Status: Examination in progress
    Family: US20210203456A1, WO2020/234567A1

---

Top CPC Codes in Results:
- H04L9/32 (15 patents): Authentication/verification
- G06F21/31 (12 patents): User authentication
- H04L9/00 (8 patents): Cryptographic mechanisms
```

## Common Use Cases

### EP Prior Art Search
1. BigQuery keyword search (country="EP")
2. Identify relevant CPC codes
3. BigQuery CPC search (country="EP")
4. EPO OPS full-text for top results
5. Document findings with citations

### Patent Family Analysis
1. Find EP patent via BigQuery or EPO OPS
2. Get family_id
3. Search for family members worldwide
4. Map filing strategy across jurisdictions
5. Check legal status in each country

### EP Freedom-to-Operate
1. Search EP patents in relevant technology
2. Filter for granted patents (B1/B2)
3. Check legal status (in force vs expired)
4. Identify validated countries
5. Assess infringement risk

### EP Opposition Research
1. Find granted EP patents (B1)
2. Check if within 9-month opposition window
3. Search for prior art predating priority date
4. Analyze claims scope
5. Assess opposition grounds (Art. 100 EPC)

## Performance & Coverage

| Method | Patents | Coverage | Speed | Cost |
|--------|---------|----------|-------|------|
| BigQuery (EP) | ~5M EP | EP applications + grants | 3-4s | Free* |
| EPO OPS | All EP | Full text + legal status | 1-3s | Free** |

*BigQuery free tier: 1TB queries/month (~20,000 searches)
**EPO OPS: Fair use (2.5GB data traffic per week)

## Tools Available

- **Bash**: To run search scripts
- **Read**: To load saved search results
- **Write**: To save patent search results
