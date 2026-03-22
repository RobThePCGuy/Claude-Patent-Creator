"""Base class for hybrid RAG indices (FAISS + BM25 + HyDE + Reranking)"""

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

try:
    import faiss
    from sentence_transformers import CrossEncoder, SentenceTransformer
except ImportError:
    print(
        "Missing dependencies. Install with: pip install sentence-transformers faiss-cpu torch",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from rank_bm25 import BM25Okapi as BM25OkapiType
else:
    BM25OkapiType = Any  # type: ignore[misc,assignment]

from utils.device import get_device


class HybridRAGIndex(ABC):
    """Base class for hybrid retrieval-augmented generation indices

    Architecture: FAISS vector search + BM25 keyword search + HyDE expansion + Cross-encoder reranking

    Subclasses must implement:
    - _build_chunks(): Process source documents into searchable chunks
    - _get_index_files(): Return paths for index storage
    """

    # Model names (can be overridden in subclasses)
    EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, use_hyde: bool = True):
        """Initialize hybrid RAG index

        Args:
            use_hyde: Enable HyDE query expansion (default: True)
        """
        # Device detection
        self.device = get_device()

        # Embedding model
        print(f"Loading embedding model ({self.EMBEDDING_MODEL})...", file=sys.stderr)
        self.model = SentenceTransformer(self.EMBEDDING_MODEL, device=self.device)

        # Reranker model
        print(f"Loading reranker ({self.RERANKER_MODEL})...", file=sys.stderr)
        self.reranker = CrossEncoder(self.RERANKER_MODEL, device=self.device)

        # HyDE query expander
        self.use_hyde = use_hyde
        self.hyde_expander = None
        if use_hyde:
            try:
                from hyde import HyDEQueryExpander

                self.hyde_expander = HyDEQueryExpander(backend="auto")
            except Exception as e:
                print(f"HyDE initialization failed: {e}. Continuing without HyDE.", file=sys.stderr)
                self.use_hyde = False

        # Storage
        self.chunks: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        self.index: Optional[faiss.Index] = None
        self.bm25: Optional[BM25OkapiType] = None

    @abstractmethod
    def _build_chunks(self) -> None:
        """Build chunks and metadata from source documents

        Must populate:
        - self.chunks: List of text chunks
        - self.metadata: List of metadata dicts (one per chunk)
        """
        pass

    @abstractmethod
    def _get_index_files(self) -> Dict[str, Path]:
        """Return paths for index files

        Returns:
            Dict with keys: 'faiss', 'metadata', 'bm25'
        """
        pass

    def build_index(self) -> None:
        """Build FAISS and BM25 indices from chunks"""
        print("Building chunks...", file=sys.stderr)
        self._build_chunks()

        if not self.chunks:
            raise ValueError("No chunks generated. Cannot build index.")

        print(f"Encoding {len(self.chunks)} chunks...", file=sys.stderr)

        # Build FAISS vector index
        embeddings = self.model.encode(
            self.chunks, batch_size=32, show_progress_bar=True, convert_to_numpy=True
        )

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        # Create FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(
            dimension
        )  # Inner product = cosine similarity with normalized vectors
        self.index.add(embeddings)  # type: ignore[arg-type]

        # Build BM25 index
        if BM25Okapi:
            print("Building BM25 index...", file=sys.stderr)
            tokenized_corpus = [chunk.lower().split() for chunk in self.chunks]
            self.bm25 = BM25Okapi(tokenized_corpus)

        print("Index built successfully", file=sys.stderr)

    def save_index(self) -> None:
        """Save index to disk"""
        if self.index is None:
            raise ValueError("Index not built. Call build_index() first.")

        files = self._get_index_files()

        # Save FAISS index
        faiss.write_index(self.index, str(files["faiss"]))
        print(f"FAISS index saved to {files['faiss']}", file=sys.stderr)

        # Save metadata
        with open(files["metadata"], "w") as f:
            json.dump(self.metadata, f)
        print(f"Metadata saved to {files['metadata']}", file=sys.stderr)

        # Save BM25 index
        if self.bm25:
            import pickle

            with open(files["bm25"], "wb") as f:
                pickle.dump(self.bm25, f)
            print(f"BM25 index saved to {files['bm25']}", file=sys.stderr)

    def load_index(self) -> bool:
        """Load index from disk

        Returns:
            True if loaded successfully, False otherwise
        """
        files = self._get_index_files()

        if not files["faiss"].exists() or not files["metadata"].exists():
            return False

        try:
            # Load FAISS index
            self.index = faiss.read_index(str(files["faiss"]))

            # Load metadata
            with open(files["metadata"], "r") as f:
                self.metadata = json.load(f)

            # Rebuild chunks from metadata
            self.chunks = [m.get("text", "") for m in self.metadata]

            # Load BM25 if available
            if files["bm25"].exists():
                import pickle

                with open(files["bm25"], "rb") as f:
                    self.bm25 = pickle.load(f)

            print(f"Index loaded: {len(self.chunks)} chunks", file=sys.stderr)
            return True

        except Exception as e:
            print(f"Failed to load index: {e}", file=sys.stderr)
            return False

    def _hybrid_search(
        self, query: str, retrieve_k: int, apply_hyde: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """Perform hybrid search with FAISS + BM25 + optional HyDE

        Args:
            query: Search query
            retrieve_k: Number of candidates to retrieve
            apply_hyde: Apply HyDE query expansion

        Returns:
            Dict mapping chunk indices to candidate info (text, metadata, scores)
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_index() or load_index() first.")

        # HyDE query expansion
        queries_to_search = [query]
        if apply_hyde and self.use_hyde and self.hyde_expander:
            try:
                expanded_queries = self.hyde_expander.expand_query(query, num_expansions=3)
                queries_to_search = expanded_queries
                print(f"HyDE: Expanded to {len(queries_to_search)} queries", file=sys.stderr)
            except Exception as e:
                print(f"HyDE expansion failed: {e}, using original query", file=sys.stderr)

        candidates = {}

        # Search with each query variant
        for query_idx, search_query in enumerate(queries_to_search):
            query_weight = 1.0 if query_idx == 0 else 0.5  # Weight original query higher

            # Vector search
            query_embedding = self.model.encode([f"query: {search_query}"])
            query_embedding = query_embedding.astype("float32")
            faiss.normalize_L2(query_embedding)

            distances, indices = self.index.search(query_embedding, retrieve_k)  # type: ignore[arg-type]

            # Add vector search results with RRF scoring
            for rank, (idx, dist) in enumerate(zip(indices[0], distances[0])):
                if idx < 0 or idx >= len(self.chunks):  # Skip invalid indices
                    continue

                rrf_contribution = query_weight * (1.0 / (60 + rank + 1))

                if idx in candidates:
                    candidates[idx]["rrf_score"] += rrf_contribution
                    candidates[idx]["vector_score"] = max(
                        candidates[idx].get("vector_score", 0),
                        float(dist),  # Cosine similarity (already 0-1)
                    )
                else:
                    candidates[idx] = {
                        "text": self.chunks[idx],
                        "metadata": self.metadata[idx],
                        "vector_score": float(dist),
                        "rrf_score": rrf_contribution,
                    }

            # BM25 keyword search
            if self.bm25:
                tokenized_query = search_query.lower().split()
                bm25_scores = self.bm25.get_scores(tokenized_query)
                bm25_top_indices = np.argsort(bm25_scores)[::-1][:retrieve_k]

                for rank, idx in enumerate(bm25_top_indices):
                    if idx >= len(self.chunks):  # Skip invalid indices
                        continue

                    rrf_contribution = query_weight * (1.0 / (60 + rank + 1))

                    if idx in candidates:
                        candidates[idx]["rrf_score"] += rrf_contribution
                        candidates[idx]["bm25_score"] = max(
                            candidates[idx].get("bm25_score", 0), float(bm25_scores[idx])
                        )
                    else:
                        candidates[idx] = {
                            "text": self.chunks[idx],
                            "metadata": self.metadata[idx],
                            "bm25_score": float(bm25_scores[idx]),
                            "rrf_score": rrf_contribution,
                        }

        return candidates

    def _rerank_candidates(
        self, query: str, candidates: Dict[int, Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """Rerank candidates using cross-encoder

        Args:
            query: Original search query
            candidates: Dict of candidate chunks
            top_k: Number of final results to return

        Returns:
            List of top_k reranked results
        """
        # Sort by RRF score
        sorted_candidates = sorted(
            candidates.items(), key=lambda x: x[1]["rrf_score"], reverse=True
        )

        if not sorted_candidates:
            return []

        # Rerank top candidates with cross-encoder
        rerank_candidates = sorted_candidates[: top_k * 2]  # Rerank 2x more than needed

        pairs = [(query, cand[1]["text"]) for cand in rerank_candidates]
        rerank_scores = self.reranker.predict(pairs)

        # Combine scores and return top_k
        results = []
        for (idx, cand), rerank_score in zip(rerank_candidates, rerank_scores):
            results.append(
                {
                    **cand,
                    "rerank_score": float(rerank_score),
                    "final_score": float(rerank_score),  # Use rerank score as final score
                }
            )

        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:top_k]
