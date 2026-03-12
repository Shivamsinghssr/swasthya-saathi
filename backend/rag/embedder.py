"""
rag/embedder.py

BGE embedder via FastEmbed (ONNX Runtime backend).
Replaces sentence-transformers to keep Docker image under 4GB.
Same BGE model, same vector quality, ~10x smaller install.
"""
import numpy as np
from typing import List
from fastembed import TextEmbedding
import config


class Embedder:
    """
    FastEmbed uses ONNX Runtime — no PyTorch dependency.
    BGE-small produces 384-dim normalized vectors.
    """

    def __init__(self, model_name: str = config.EMBED_MODEL):
        print(f"[Embedder] Loading: {model_name}")
        self.model = TextEmbedding(model_name=model_name)
        self.dim   = 384  # BGE-small-en-v1.5 output dimension
        print(f"[Embedder] Ready. dim={self.dim}")

    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        embeddings = list(self.model.embed(texts))
        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        # FastEmbed handles query prefix internally for BGE models
        embeddings = list(self.model.query_embed(query))
        return np.array(embeddings[0], dtype=np.float32)
