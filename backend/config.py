"""
config.py — Central config for Swasthya Saathi.
All settings live here. Never hardcode values elsewhere.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# llama-3.3-70b has strong tool-calling support on Groq
LLM_MODEL = "llama-3.3-70b-versatile"

# ── Embedder ──────────────────────────────────────────────────────────────────
# Same model used in production — fast on CPU, good quality
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 80

# ── Retrieval ──────────────────────────────────────────────────────────────────
TOP_K_BM25  = 8
TOP_K_FINAL = 3
RRF_K       = 60

# ── Index paths (built once by build_indexes.py, loaded at startup) ────────────
SYMPTOMS_INDEX_PATH  = "indexes/symptoms.faiss"
MEDICINES_INDEX_PATH = "indexes/medicines.faiss"
SCHEMES_INDEX_PATH   = "indexes/schemes.faiss"

# ── Static data ────────────────────────────────────────────────────────────────
HEALTH_CENTERS_PATH = "data/health_centers/up_bihar_phc.json"

# ── Data source paths ──────────────────────────────────────────────────────────
SYMPTOMS_DATA_PATH  = "data/symptoms/"
MEDICINES_DATA_PATH = "data/medicines/"
SCHEMES_DATA_PATH   = "data/schemes/"
