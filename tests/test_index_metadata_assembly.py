"""Index metadata assembly must accept every source's chunk shape.

build_index hard-keyed c["page"]/c["file"]/c["section"], but the EPO/PCT
extractors emit chunks via _chunk_text_with_metadata whose base metadata
has no "page" — so the first rebuild after the #49 corpus wiring crashed
with KeyError: 'page' and the EPO corpus could never be indexed.
"""

from mcp_server.mpep_search import MPEPIndex


def test_mpep_chunk_keeps_its_fields():
    meta = MPEPIndex._chunk_to_metadata(
        {"source": "MPEP", "file": "mpep-2100.pdf", "page": 41,
         "section": "MPEP 2100", "has_statute": True}
    )
    assert meta["file"] == "mpep-2100.pdf"
    assert meta["page"] == 41
    assert meta["section"] == "MPEP 2100"
    assert meta["has_statute"] is True


def test_epo_guidelines_chunk_without_page_is_accepted():
    meta = MPEPIndex._chunk_to_metadata(
        {"source": "EPO_GUIDELINES", "file": "epo_guidelines.txt",
         "section": "EPO Guidelines Part A", "part": "Part A",
         "is_statute": False}
    )
    assert meta["page"] is None
    assert meta["section"] == "EPO Guidelines Part A"
    assert meta["part"] == "Part A", "EPO part must survive into the index"


def test_bare_chunk_never_raises():
    meta = MPEPIndex._chunk_to_metadata({"source": "EPC"})
    assert meta["file"] == ""
    assert meta["page"] is None
    assert meta["section"] == "EPC"


def test_cfr_and_subsequent_fields_still_pass_through():
    cfr = MPEPIndex._chunk_to_metadata(
        {"source": "37_CFR", "file": "r.pdf", "page": 1, "section": "37 CFR 1.75",
         "part": "1", "is_fee_schedule": True}
    )
    assert cfr["part"] == "1" and cfr["is_fee_schedule"] is True

    sub = MPEPIndex._chunk_to_metadata(
        {"source": "SUBSEQUENT", "file": "s.pdf", "page": 2, "section": "Updates",
         "doc_type": "notice", "fr_citation": "89 FR 1", "effective_date": "2026-01-01",
         "mpep_sections_affected": ["2173"], "supersedes_mpep": True}
    )
    assert sub["doc_type"] == "notice"
    assert sub["mpep_sections_affected"] == ["2173"]
