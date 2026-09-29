---
name: patent-search
description: Search 100M+ patents via the MCP server's BigQuery tools. No standalone scripts; everything goes through the MCP tools registered by the patent-creator server.
---

# Patent Search Skill

This skill points Claude at the BigQuery patent-search tools registered by the patent-creator MCP server. Call the tools directly; do not shell out to Python.

## When to use

- Find prior art by keyword, classification, or family.
- Pull full patent records (title, abstract, claims, description) for US patents.
- Cross-reference an EP/WO patent into its US family member to get full text.

## Available MCP tools

| Tool | What it does |
|------|--------------|
| `search_patents_bigquery` | Keyword search across abstract / title / claims (US only for claims). |
| `get_patent_bigquery` | Patent details by publication number: bibliographic data + claims by default; abstract and description are opt-in. |
| `get_patents_bigquery` | Same, for up to 50 patents in one query at the cost of one lookup. |
| `search_patents_by_cpc_bigquery` | Search by CPC classification prefix. |
| `search_patents_by_ipc_bigquery` | Search by IPC classification prefix (good for older or non-US patents). |
| `search_patent_family_bigquery` | All publications sharing a family ID across jurisdictions. |
| `check_bigquery_status` | Verify auth and quota project before a long workflow. |

## Cost notes

BigQuery on-demand pricing is $6.25 / TiB (1 TiB free per month). The MCP server enforces a per-query bytes-billed ceiling, defaulting to 350 GiB. Override via `PATENT_BIGQUERY_MAX_BYTES_BILLED` if you need a larger scan window.

The patents table is unclustered, so a detail lookup costs the same for one patent or fifty; the cost depends only on which sections are requested:

| Detail lookup | Scan | Cost |
|---|---|---|
| Bibliographic only (`include_claims=False`): title, dates, family_id, CPC/IPC | ~44 GiB | ~$0.27 |
| Default: + claims | ~160 GiB | ~$1 |
| + abstract (`include_abstract=True`) | +~200 GiB | exceeds the default cap together with claims |
| + description (`include_description=True`) | ~1.1 TiB | exceeds the default cap |

So: batch with `get_patents_bigquery`, pass `include_claims=False` when you only need codes or `family_id`, and take abstracts from the search results rather than re-fetching them.

## Choosing keywords

- 2-3 keywords work better than long phrases (BigQuery `LIKE` matching is literal).
- For non-US patents, `claims` is empty in the dataset; the MCP keyword tool already searches title/abstract for those jurisdictions. For full text on EP/WO, use the EPO OPS tools instead.
- Use `search_patent_family_bigquery` to bridge from an EP/WO hit to its US family member when you need claims.

## Common workflows

**Prior art sweep:**
1. `search_patents_bigquery(query=…, country="US")` — broad scan.
2. Pick the top hits' CPC codes with one `get_patents_bigquery(patent_numbers=[…], include_claims=False)`.
3. `search_patents_by_cpc_bigquery(cpc_code=…)` — pull adjacent technology.

**Cross-jurisdiction lookup:**
1. `search_patents_bigquery(query=…, country="EP")`.
2. For the EP hits, one `get_patents_bigquery(patent_numbers=[…], include_claims=False)` to get their `family_id`s.
3. `search_patent_family_bigquery(family_id=…)` to find the US member with full claims.
