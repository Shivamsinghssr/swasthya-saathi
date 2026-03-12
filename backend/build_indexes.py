"""
build_indexes.py

Run this ONCE before starting the server to build FAISS indexes.
After this, the server loads existing indexes at startup (fast).

Usage:
    cd backend
    python build_indexes.py
"""
import os
import sys

# Ensure imports resolve from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.embedder import Embedder
from rag.indexer import _build_index, _load_txt_files
import config


def main():
    print("=" * 55)
    print("  Swasthya Saathi — Index Builder")
    print("=" * 55)

    embedder = Embedder(config.EMBED_MODEL)

    jobs = [
        ("Symptoms",  config.SYMPTOMS_DATA_PATH,  config.SYMPTOMS_INDEX_PATH),
        ("Medicines", config.MEDICINES_DATA_PATH, config.MEDICINES_INDEX_PATH),
        ("Schemes",   config.SCHEMES_DATA_PATH,   config.SCHEMES_INDEX_PATH),
    ]

    for label, data_dir, index_path in jobs:
        print(f"\n📂 Building {label} index...")
        docs = _load_txt_files(data_dir)
        if not docs:
            print(f"   ⚠️  No data files found in {data_dir} — skipping.")
            continue
        _build_index(data_dir, index_path, embedder)
        print(f"   ✅ {label} index saved → {index_path}")

    print("\n✅ All indexes built. You can now start the server.")
    print("   Run: uvicorn main:app --reload\n")


if __name__ == "__main__":
    main()
