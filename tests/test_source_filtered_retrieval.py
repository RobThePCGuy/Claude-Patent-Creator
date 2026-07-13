"""Source-filtered search must filter at retrieval, not after ranking.

search() retrieved the global top retrieve_k (<=50) candidates from the
whole unified index and only then applied source_filter. With 45.7K MPEP
chunks versus ~5K per EPO/PCT source, minority-source candidates get
squeezed out of the global cut: measured on a live fully-indexed corpus,
a source-filtered EPC_RULES search returned 1 of the 5 requested results.
Restricting retrieval to the allowed ids up front makes filtered recall
exact instead of query-dependent.
"""

import numpy as np

from mcp_server.mpep_search import MPEPIndex


def test_source_id_map_groups_by_source():
    metadata = [
        {"source": "MPEP"},
        {"source": "EPC_RULES"},
        {"source": "MPEP"},
        {"source": "EPO_GUIDELINES"},
        {"source": "EPC_RULES"},
    ]
    id_map = MPEPIndex._source_id_map(metadata)
    assert id_map["MPEP"].tolist() == [0, 2]
    assert id_map["EPC_RULES"].tolist() == [1, 4]
    assert id_map["EPO_GUIDELINES"].tolist() == [3]
    assert id_map["EPC_RULES"].dtype == np.int64


def test_masked_bm25_top_returns_only_allowed_indices():
    scores = np.array([9.0, 1.0, 8.0, 7.0, 0.5])
    allowed = np.array([1, 3, 4], dtype=np.int64)

    top = MPEPIndex._masked_bm25_top(scores, allowed, k=2)

    assert top.tolist() == [3, 1], "highest-scoring ALLOWED indices, in order"


def test_masked_bm25_top_without_mask_is_global():
    scores = np.array([1.0, 5.0, 3.0])

    top = MPEPIndex._masked_bm25_top(scores, None, k=2)

    assert top.tolist() == [1, 2]


def test_masked_bm25_top_handles_k_larger_than_allowed():
    scores = np.array([1.0, 5.0, 3.0, 2.0])
    allowed = np.array([0], dtype=np.int64)

    top = MPEPIndex._masked_bm25_top(scores, allowed, k=10)

    assert top.tolist() == [0]
