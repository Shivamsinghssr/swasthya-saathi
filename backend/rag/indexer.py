"""
rag/indexer.py

Builds FAISS indexes from text files, or loads existing ones.
Run build_indexes.py once before starting the server.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Any
import json

from rag.embedder import Embedder
from rag.vector_store import FAISSVectorStore, Chunk
from rag.retriever import HybridRetriever
import config


# ── Chunker ────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, source: str) -> List[Chunk]:
    """Recursive chunker respecting paragraph and sentence boundaries."""
    separators = ["\n\n", "\n", ". ", "! ", "? ", " "]
    chunks     = _rec_split(text, separators)
    return [
        Chunk(text=c.strip(), chunk_id=f"{source}_{i}", metadata={"source": source})
        for i, c in enumerate(chunks)
        if c.strip()
    ]


def _rec_split(text: str, seps: List[str]) -> List[str]:
    if not seps or len(text) <= config.CHUNK_SIZE:
        return [text]
    sep    = seps[0]
    parts  = text.split(sep) if sep else list(text)
    result, current = [], ""
    for part in parts:
        candidate = (current + (sep if current else "") + part)
        if len(candidate) <= config.CHUNK_SIZE:
            current = candidate
        else:
            if current:
                result.append(current)
            current = part if len(part) <= config.CHUNK_SIZE else _rec_split(part, seps[1:])[0]
    if current:
        result.append(current)
    # Add overlap
    if len(result) > 1:
        overlapped = [result[0]]
        for i in range(1, len(result)):
            tail = " ".join(result[i - 1].split()[-(config.CHUNK_OVERLAP // 4):])
            overlapped.append(tail + " " + result[i])
        return overlapped
    return result


# ── File loader ────────────────────────────────────────────────────────────────

def _load_txt_files(directory: str) -> List[Dict[str, str]]:
    docs = []
    base = Path(directory)
    if not base.exists():
        print(f"⚠️  Directory not found: {directory}")
        return docs
    for fp in sorted(base.glob("*.txt")):
        text = fp.read_text(encoding="utf-8").strip()
        if text:
            docs.append({"text": text, "source": fp.stem})
    print(f"[Indexer] Loaded {len(docs)} files from {directory}")
    return docs


# ── Build one index ────────────────────────────────────────────────────────────

def _build_index(
    data_dir: str,
    index_path: str,
    embedder: Embedder,
) -> HybridRetriever:
    docs   = _load_txt_files(data_dir)
    chunks = []
    for doc in docs:
        chunks.extend(_chunk_text(doc["text"], doc["source"]))

    print(f"[Indexer] {len(chunks)} chunks from {data_dir}")

    vs = FAISSVectorStore(embedder.dim, index_path)

    if chunks:
        embeddings = embedder.embed([c.text for c in chunks])
        vs.add(chunks, embeddings)
        vs.save()
    else:
        print(f"⚠️  No chunks found for {data_dir} — index will be empty.")

    retriever = HybridRetriever(vs, embedder)
    return retriever


# ── Public API ─────────────────────────────────────────────────────────────────

def load_or_build_indexes() -> Tuple[Dict[str, HybridRetriever], List[Any]]:
    """
    Called once at server startup.
    Loads existing indexes if present, else builds from data files.
    Returns dict of retrievers + health centers list.
    """
    embedder = Embedder(config.EMBED_MODEL)

    retrievers = {}

    for name, data_dir, index_path in [
        ("symptoms",  config.SYMPTOMS_DATA_PATH,  config.SYMPTOMS_INDEX_PATH),
        ("medicines", config.MEDICINES_DATA_PATH, config.MEDICINES_INDEX_PATH),
        ("schemes",   config.SCHEMES_DATA_PATH,   config.SCHEMES_INDEX_PATH),
    ]:
        vs = FAISSVectorStore(embedder.dim, index_path)
        if vs.load():
            retriever = HybridRetriever(vs, embedder)
        else:
            print(f"[Indexer] Index not found for '{name}' — building now...")
            retriever = _build_index(data_dir, index_path, embedder)
        retrievers[name] = retriever

    # Load health centers JSON
    health_centers = []
    hc_path = Path(config.HEALTH_CENTERS_PATH)
    if hc_path.exists():
        with open(hc_path, "r", encoding="utf-8") as f:
            health_centers = json.load(f)
        print(f"[Indexer] Loaded {len(health_centers)} health centers.")
    else:
        print(f"⚠️  Health centers file not found: {hc_path}")

    return retrievers, health_centers
