---
description: Search European patents using EPO OPS API and BigQuery (100M+ patents filtered for EP)
argument-hint: "query [optional: --cpc CODE] [--year-range START-END] [--applicant NAME] [--limit N]"
allowed-tools:
  - search_epo_patents
  - search_patents_bigquery
  - get_patent_bigquery
  - get_patents_bigquery
  - search_patents_by_cpc_bigquery
model: claude-sonnet-4-5-20250929
---

# EPO Patent Search

Search European patents using the EPO Open Patent Services (OPS) API and Google BigQuery.

**Query:** $ARGUMENTS

## What This Command Does

Provides two complementary European patent search methods:

1. **EPO OPS API** - Official EPO database with full-text EP publications, legal status, patent family links
2. **BigQuery** (country="EP") - 100M+ worldwide patents filtered for European patents, fast keyword/CPC search

## Search Methods

### EPO OPS API (Detailed EP Data)

Best for:
- Full-text EP patent retrieval
- Legal status and procedural history
- Patent family linking (INPADOC families)
- Applicant/inventor search
- EP publication details (A1, A2, B1, B2)

```
/search-epo "blockchain authentication"

> Searching EPO OPS for EP patents...
>
> [1] EP3456789A1 - Authentication system using distributed ledger
>     Applicant: Example GmbH
>     Filed: 2019-03-15 | Published: 2020-01-22
>     IPC: H04L9/32, G06F21/31
>     Status: Examination in progress
>
> [2] EP3567890B1 - Blockchain-based identity verification
>     Applicant: Tech Corp
>     Filed: 2018-07-20 | Granted: 2021-05-12
>     IPC: H04L9/00, G06Q20/38
>     Status: Patent in force
```

### BigQuery (Fast Broad Search)

Best for:
- Quick keyword search across EP patents
- CPC classification browsing
- Filing trend analysis
- Cross-jurisdiction comparison (EP vs US vs CN)

```
/search-epo "neural network medical imaging" --cpc G06N --limit 20

> Searching BigQuery for EP patents...
>
> Found: 156 EP patents matching query
> Showing top 20 results
>
> [1] EP-3891234-A1 - Deep learning system for medical image analysis
>     Assignee: Medical AI Inc.
>     Filed: 2020-06-15
>     CPC: G06N3/08, A61B6/00
>     ...
```

## Combined Workflow

For comprehensive EP patent research:

1. **Start with BigQuery** - Broad keyword search, filter country="EP"
2. **Identify CPC codes** - Extract from relevant results
3. **Deep CPC search** - BigQuery CPC search for thorough coverage
4. **EPO OPS details** - Get full text, legal status, family data
5. **Family analysis** - Use family_id to find related filings worldwide

```
> Step 1: BigQuery broad search
search_patents_bigquery("voice biometric", country="EP", limit=20)

> Step 2: Found CPC G10L17, search more
search_patents_by_cpc_bigquery("G10L17", country="EP", limit=50)

> Step 3: Get full details for top results
search_epo_patents("EP3456789")  # Full text, legal status, family

> Step 4: Check patent family
# Use family_id to find US, CN, JP counterparts
```

## Search Options

**By Keywords**:
```
/search-epo "autonomous vehicle lidar"
```

**By CPC Code**:
```
/search-epo --cpc G01S17/89
```

**By Applicant**:
```
/search-epo --applicant "Siemens"
```

**By Year Range**:
```
/search-epo "5G antenna" --year-range 2020-2025
```

**Combined**:
```
/search-epo "battery electrode" --cpc H01M4 --year-range 2022-2025 --limit 30
```

## EP Publication Types

| Code | Meaning | Description |
|------|---------|-------------|
| A1 | Application + search report | Published with European search report |
| A2 | Application only | Published without search report |
| A3 | Search report | Search report published separately |
| B1 | Granted patent | Patent specification after grant |
| B2 | Amended patent | Patent specification after opposition |

## Result Format

Each result includes:
```
{
    "publication_number": "EP3456789A1",
    "title": "Authentication system using distributed ledger",
    "abstract": "A system for...",
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
    "full_text_available": true
}
```

## Common EP CPC Codes

| Code | Technology |
|------|-----------|
| A61B | Diagnosis/surgery |
| B60W | Vehicle control |
| C12N | Biotechnology |
| F03D | Wind motors |
| G06F | Computing |
| G06N | AI/machine learning |
| G16H | Healthcare informatics |
| H01L | Semiconductor devices |
| H04L | Digital communication |
| H04W | Wireless communication |

## Tips for EP Searches

1. **Use IPC and CPC**: EP patents are classified under both systems
2. **Check families**: Use family_id to find US/CN/JP counterparts
3. **Legal status matters**: Check if patent is in force, expired, or opposed
4. **Language**: EP patents published in EN, FR, or DE - search all
5. **A1 vs B1**: A1 is application (claims may change), B1 is granted
6. **Opposition period**: 9 months after grant for third-party opposition

## After the Search

Based on results, I can help you:

1. **Analyze prior art**: Compare findings to your invention
2. **Draft claims**: Distinguish from EP prior art found
3. **Create EP application**: Use `/create-epo-patent`
4. **Freedom-to-operate**: Assess EP patent landscape risks
5. **Family analysis**: Track patents across jurisdictions

---

**DISCLAIMER:** This tool assists with patent research but does NOT replace professional patent searching by a qualified searcher. Not affiliated with or endorsed by the EPO.
