---
name: patent-search
description: Search patents with Google Patents via SerpApi, EPO OPS fallback, or optional BigQuery tools. No standalone scripts; everything goes through the MCP tools registered by the patent-creator server.
---

# Patent Search Skill

This skill points Claude at the patent-search tools registered by the patent-creator MCP server. Call the tools directly; do not shell out to Python.

## Patent search providers

Use `check_google_patents_status` first, then `search_patents_google` when SerpApi is configured. If Google Patents is not ready, call `check_epo_api_status`: when it is ready, `search_epo_patents` searches worldwide patent titles and abstracts (CQL `ta=` keywords) and classes (`cpc=` or `ic=` codes), and `get_epo_patent` retrieves claims and description where OPS supplies full text (EP, WO and selected national publications; not every worldwide hit). Check the actual text: empty fields or "not found/not available" messages are not a successful read. Successful OPS keyword/class searches count as patent search, with coverage limits recorded. `search_uspto_api` (after `check_uspto_api_status`) adds US application records via ODP application metadata queries (including titles, parties and status), without claims/description full-text search; use it only as a supplement. BigQuery is optional: call any `*_bigquery` tool only after `check_bigquery_status` confirms it is available. Without BigQuery, use the ready provider: Google Patents links and keyword/CPC queries, or OPS results, `get_epo_patent`, `get_epo_patent_family` and CQL keyword/class queries. OPS search results contain publication numbers, not document URLs. Mark unavailable details, family coverage and classification searches as unverified. If none of Google Patents, EPO OPS and BigQuery is ready, report the status errors and explain how to restore a provider or set up SerpApi (README Quick Start, Step 3) and run a no-key first screen in the meantime: several `WebSearch` queries restricted to Google Patents (`allowed_domains: ["patents.google.com"]`), then read the closest patent pages with `WebFetch` for claims, dates, CPC codes and citations. Label everything found this way a web first screen, not a prior-art search: web search ranks pages rather than matching claim text and misses much of the record, so a thin or empty result is never evidence of no prior art. A first screen never supports a novelty, obviousness or patentability verdict: in every later assessment, report section or phase that would give one (including any NOVEL / LIKELY NO verdict), write "Not assessed: only a web first screen was run; set up patent search and rerun" instead.

## When to use

- Find prior art by keyword, classification, or family.
- Pull full patent records (title, abstract, claims, description) for US patents.
- Cross-reference an EP/WO patent into its US family member to get full text.

## Available MCP tools

| Tool | What it does |
|------|--------------|
| `search_patents_google` | **Recommended.** Full-text keyword search worldwide (claims and description included), one search credit per call. Needs `SERPAPI_API_KEY` (free plan: 250/month). |
| `check_google_patents_status` | Is the key set, and how many searches are left this month (free to call). |
| `check_epo_api_status` | Check OPS credentials and authentication; a subsequent search can still fail. |
| `search_epo_patents` | Worldwide title/abstract and classification search using CQL; no implicit EP filter. |
| `get_epo_patent` | Bibliographic data and available claims/description; inspect text for missing/error messages. |
| `get_epo_patent_family` | Family publications across jurisdictions. |
| `check_uspto_api_status` / `search_uspto_api` | ODP application metadata search; supplement only. |
| `search_patents_bigquery` | Fallback keyword search across title / abstract / claims (US only for claims). ~341 GiB, about $2, per search. |
| `search_non_patent_literature` | Papers and preprints (OpenAlex, arXiv, Semantic Scholar) as prior art. Free, no key. `published_before` = priority date. |
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

`search_patents_google`:
- All words must match; "double quotes" match an exact phrase. No stemming, so search synonyms and plurals separately.
- Lead with the invention's distinctive terms. Common words match thousands of patents and push the closest art down; in testing, adding "heart valve" to a query buried the target past #300, while its distinctive claim words found it at #48.
- Use `limit=100`: it costs the same one credit as `limit=10`.
- Stay inside a classification by adding a full CPC group: `"voice biometric" CPC=G10L17/00` (a bare `CPC=G10L17` finds nothing).
- Results show one row per publication, so a US patent and its EP family member can both appear.

`search_epo_patents` (fallback when Google Patents is not ready):
- Use explicit CQL: `ta="neural" and ta="network"`, `cpc="G06N3/00"`, or `ic="G06N"`. These queries pass through unchanged.
- `ta=` searches titles/abstracts, not claims. Use `get_epo_patent` for available text and `get_epo_patent_family` for related publications.
- Accepts only `query` and `limit` (maximum 100); do not copy Google Patents country/year arguments. Record result caps and unread documents as coverage limits.

`search_patents_bigquery` (optional alternative):
- 2-3 keywords work better than long phrases (BigQuery `LIKE` matching is literal).
- For non-US patents, `claims` is empty in the dataset; the MCP keyword tool already searches title/abstract for those jurisdictions. For full text on EP/WO, use the EPO OPS tools instead.
- Use `search_patent_family_bigquery` to bridge from an EP/WO hit to its US family member when you need claims.

`search_non_patent_literature`:
- Papers use academic wording, not claim language: search "lithium dendrite suppression", not "means for inhibiting growth".
- Set `published_before` to the priority date; only papers the indexes date before that day come back. Index dates are sometimes wrong, so each result's date is cross-checked with the publisher's DOI record (Crossref); a result with `date_check` must have its date confirmed on the publisher's page before it is cited as prior art. `date_source` says where each date came from; treat "index only, not cross-checked" dates with the same care. `date_note` means only an unconfirmed print date shows the paper is old enough; confirm it too before relying on it.
- Read `sources` in the result. A source marked busy or failed was not searched; say so in any report. No results is never proof that no prior art exists.

## Common workflows

**Prior art sweep:**
1. `search_patents_google(query=…, limit=100)` — broad full-text scan, worldwide (fallback: `search_epo_patents` with `ta=` CQL; optional alternative: `search_patents_bigquery(query=…, country="US")`).
2. Read Google Patents links or OPS result fields for CPC codes. If BigQuery is configured, optionally batch details with `get_patents_bigquery(patent_numbers=[…], include_claims=False)`.
3. `search_non_patent_literature(query=…, published_before="<priority date>")` — papers and preprints on the same concepts, free.
4. `search_patents_google(query="<terms> CPC=<group>/00", limit=100)` — pull adjacent technology (fallback: `search_epo_patents` with `cpc=` CQL; optional alternative: `search_patents_by_cpc_bigquery`, ~234 GiB a search).

**Cross-jurisdiction lookup:**
1. `search_patents_google(query=…, country="EP")` (fallback: OPS worldwide search with returned publication countries checked; optional alternative: `search_patents_bigquery(query=…, country="EP")`).
2. Read returned EP patent links, or use `get_epo_patent` and `get_epo_patent_family` with OPS. Report inaccessible records; OPS full text is not available for every family member.
3. If BigQuery is configured, optionally use `get_patents_bigquery(patent_numbers=[…], include_claims=False)` and `search_patent_family_bigquery(family_id=…)`.
