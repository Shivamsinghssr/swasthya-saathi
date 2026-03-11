"""
tests/test_tools.py

Basic unit tests for Swasthya Saathi tools.
Run: pytest tests/ -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.tools import (
    health_center_locator,
    prescription_reader,
    init_tools,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

class MockRetriever:
    """Minimal mock retriever for testing without FAISS."""

    def retrieve(self, query: str, top_k: int = 3):
        from rag.vector_store import Chunk
        return [
            (Chunk(text=f"Mock result for: {query}", chunk_id="mock_0"), 0.9)
        ]


@pytest.fixture(autouse=True)
def setup_tools():
    """Init tools with mock retrievers before each test."""
    import json
    health_centers = [
        {
            "name": "Test PHC Varanasi",
            "type": "Primary Health Centre",
            "district": "varanasi",
            "state": "UP",
            "address": "Test Address, Varanasi",
            "timing": "Subah 8 - Shaam 4",
            "phone": "123456",
        }
    ]
    init_tools(
        symptom_retriever  = MockRetriever(),
        medicine_retriever = MockRetriever(),
        scheme_retriever   = MockRetriever(),
        health_centers     = health_centers,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_health_center_locator_found():
    result = health_center_locator.invoke({"district": "varanasi"})
    assert "Test PHC Varanasi" in result
    assert "varanasi" in result.lower() or "Varanasi" in result


def test_health_center_locator_not_found():
    result = health_center_locator.invoke({"district": "unknown_district_xyz"})
    assert "nahi mila" in result or "104" in result


def test_prescription_reader_single():
    result = prescription_reader.invoke({"medicine_names": "Paracetamol"})
    assert "PARACETAMOL" in result
    assert "Mock result" in result


def test_prescription_reader_multiple():
    result = prescription_reader.invoke({"medicine_names": "Paracetamol, ORS, Zinc"})
    assert "PARACETAMOL" in result
    assert "ORS" in result
    assert "ZINC" in result


def test_prescription_reader_empty():
    result = prescription_reader.invoke({"medicine_names": ""})
    assert "nahi mila" in result or "likhein" in result
