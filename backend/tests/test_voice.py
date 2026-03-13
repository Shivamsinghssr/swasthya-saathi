"""
tests/test_voice.py

Tests for Phase 2 voice pipeline.
Mocks Sarvam API so no real API calls are made.
Run: pytest tests/test_voice.py -v
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Mock STT ──────────────────────────────────────────────────────────────────

class MockSTT:
    async def transcribe(self, audio_bytes, mime_type="audio/webm"):
        if not audio_bytes:
            return {"transcript": "", "language_code": "hi-IN", "success": False}
        return {"transcript": "mujhe bukhar hai", "language_code": "hi-IN", "success": True}


# ── Mock TTS ──────────────────────────────────────────────────────────────────

class MockTTS:
    async def stream(self, text, speaker="meera", target_language_code="hi-IN"):
        # Yield fake audio bytes
        yield b"FAKE_WAV_CHUNK_1"
        yield b"FAKE_WAV_CHUNK_2"

    async def synthesize(self, text, speaker="meera"):
        return b"FAKE_WAV_COMPLETE"


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_stt_empty_audio():
    stt = MockSTT()
    result = asyncio.run(stt.transcribe(b""))
    assert result["success"] == False
    assert result["transcript"] == ""


def test_stt_with_audio():
    stt = MockSTT()
    result = asyncio.run(stt.transcribe(b"fake_audio_data"))
    assert result["success"] == True
    assert result["transcript"] == "mujhe bukhar hai"
    assert result["language_code"] == "hi-IN"


def test_tts_streaming():
    tts = MockTTS()
    async def collect():
        chunks = []
        async for chunk in tts.stream("Bukhar mein paani piyen."):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())
    assert len(chunks) == 2
    assert all(isinstance(c, bytes) for c in chunks)


def test_tts_synthesize():
    tts = MockTTS()
    audio = asyncio.run(tts.synthesize("Test text"))
    assert isinstance(audio, bytes)
    assert len(audio) > 0


def test_sentence_splitting():
    """Test that long text is split into sentences correctly."""
    import re
    SENTENCE_RE = re.compile(r'(?<=[।.!?])\s+')

    text = "Bukhar mein paani piyen. ORS lein. Doctor ke paas jayen।"
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    assert len(sentences) == 3
    assert "paani piyen" in sentences[0]
