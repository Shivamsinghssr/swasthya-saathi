"""
rag/retriever.py

Hybrid retrieval: BM25 + Dense (FAISS) fused via RRF.
Same battle-tested pattern from production codebase.
"""
import numpy as np
from typing import List, Tuple, Dict
from rank_bm25 import BM25Okapi

from rag.vector_store import FAISSVectorStore, Chunk
from rag.embedder import Embedder
import config


class HybridRetriever:
    """
    RRF formula:  score(doc) = Σ  1 / (k + rank_i)
    Combines BM25 keyword matching + dense semantic search.
    """

    def __init__(self, vs: FAISSVectorStore, embedder: Embedder):
        self.vs       = vs
        self.embedder = embedder
        self.bm25: BM25Okapi = None
        self._build_bm25()

    def _build_bm25(self):
        if self.vs.chunks:
            tokenized = [c.text.lower().split() for c in self.vs.chunks]
            self.bm25 = BM25Okapi(tokenized)
            print(f"[Retriever] BM25 built on {len(tokenized)} chunks.")

    def rebuild_bm25(self):
        self._build_bm25()

    def _bm25_results(self, query: str, k: int) -> List[Tuple[int, float]]:
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(query.lower().split())
        top    = np.argsort(scores)[::-1][:k]
        return [(int(i), float(scores[i])) for i in top]

    def _dense_results(self, query: str, k: int) -> List[Tuple[int, float]]:
        qemb    = self.embedder.embed_query(query)
        results = self.vs.search(qemb, k)
        c2idx   = {id(c): i for i, c in enumerate(self.vs.chunks)}
        return [(c2idx[id(ch)], sc) for ch, sc in results]

    def _rrf(self, bm25_r, dense_r, k: int = config.RRF_K) -> List[Tuple[int, float]]:
        scores: Dict[int, float] = {}
        for rank, (idx, _) in enumerate(bm25_r, 1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
        for rank, (idx, _) in enumerate(dense_r, 1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def retrieve(self, query: str, top_k: int = config.TOP_K_FINAL) -> List[Tuple[Chunk, float]]:
        bm25_r  = self._bm25_results(query, config.TOP_K_BM25)
        dense_r = self._dense_results(query, config.TOP_K_BM25)
        fused   = self._rrf(bm25_r, dense_r)
        return [
            (self.vs.chunks[i], s)
            for i, s in fused[:top_k]
            if i < len(self.vs.chunks)
        ]
