"""
rag/vector_store.py

FAISS IndexFlatIP = cosine similarity (with normalized vectors).
"""
import faiss
import numpy as np
import pickle
import os
from typing import List, Tuple
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    chunk_id: str
    metadata: dict = field(default_factory=dict)


class FAISSVectorStore:

    def __init__(self, dim: int, path: str):
        self.dim       = dim
        self.path      = path
        self.meta_path = path + ".meta"
        self.chunks: List[Chunk] = []
        self.index     = faiss.IndexFlatIP(dim)

    def add(self, chunks: List[Chunk], embeddings: np.ndarray):
        self.index.add(embeddings.astype(np.float32))
        self.chunks.extend(chunks)

    def search(self, query_emb: np.ndarray, top_k: int) -> List[Tuple[Chunk, float]]:
        q = query_emb.reshape(1, -1).astype(np.float32)
        scores, idxs = self.index.search(q, min(top_k, self.index.ntotal))
        return [
            (self.chunks[i], float(s))
            for s, i in zip(scores[0], idxs[0])
            if i != -1
        ]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        faiss.write_index(self.index, self.path)
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.chunks, f)
        print(f"[VectorStore] Saved {self.index.ntotal} vectors → {self.path}")

    def load(self) -> bool:
        if os.path.exists(self.path) and os.path.exists(self.meta_path):
            self.index = faiss.read_index(self.path)
            with open(self.meta_path, "rb") as f:
                self.chunks = pickle.load(f)
            print(f"[VectorStore] Loaded {self.index.ntotal} vectors ← {self.path}")
            return True
        return False

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)
