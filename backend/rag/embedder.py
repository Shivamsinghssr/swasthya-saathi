"""
rag/embedder.py

BGE embedder with L2 normalization.
Identical pattern to production codebase — familiar ground.
"""
import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer
import config


class Embedder:
    """
    BGE models need a query prefix for best retrieval performance.
    All embeddings are L2-normalized → dot product == cosine similarity.
    """

    def __init__(self, model_name: str = config.EMBED_MODEL):
        print(f"[Embedder] Loading: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dim   = self.model.get_sentence_embedding_dimension()
        print(f"[Embedder] Ready. dim={self.dim}")

    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 20,
        )

    def embed_query(self, query: str) -> np.ndarray:
        prefixed = f"Represent this sentence for searching relevant passages: {query}"
        return self.model.encode([prefixed], normalize_embeddings=True)[0]
