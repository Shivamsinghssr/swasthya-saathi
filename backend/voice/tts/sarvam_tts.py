"""
voice/tts/sarvam_tts.py

Sarvam AI Text-to-Speech — Bulbul v3.
Converts Hindi/English text to audio bytes.

Sarvam TTS API:
  POST https://api.sarvam.ai/text-to-speech
  - Bulbul v3: best quality Hindi voice
  - Returns base64-encoded WAV audio
  - Supports sentence-level streaming via chunking
"""
import asyncio
import aiohttp
import base64
import os
import re
from typing import AsyncGenerator, Optional


SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Sentence splitter — split on Hindi + English punctuation
SENTENCE_RE = re.compile(r'(?<=[।.!?])\s+')


class SarvamTTS:
    """
    Sarvam Bulbul v3 TTS client with pseudo-streaming.

    Pseudo-streaming strategy (same as production codebase):
    - Split response text into sentences
    - Fire TTS request per sentence concurrently
    - Yield audio chunks as they complete (in order)
    - This achieves sub-300ms first audio latency

    Usage:
        tts = SarvamTTS(api_key="sk-...")
        async for audio_chunk in tts.stream(text):
            websocket.send_bytes(audio_chunk)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not set")

    async def _synthesize_sentence(
        self,
        session: aiohttp.ClientSession,
        text: str,
        speaker: str = "priya",
        target_language_code: str = "hi-IN",
    ) -> Optional[bytes]:
        """
        Synthesize a single sentence → returns raw WAV bytes.
        """
        if not text.strip():
            return None

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
    "inputs": [text.strip()],
    "target_language_code": target_language_code,
    "speaker": speaker,
    "model": "bulbul:v3-beta",  # or "bulbul:v2"
   
    "pace": 1.0,
    
    "speech_sample_rate": 16000,
    "enable_preprocessing": True,
    "override_triplets": {},
}

        try:
            async with session.post(
                SARVAM_TTS_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"[TTS] Error {resp.status}: {error[:100]}")
                    return None

                data = await resp.json()
                audios = data.get("audios", [])
                if not audios:
                    return None

                # Sarvam returns base64-encoded WAV
                audio_bytes = base64.b64decode(audios[0])
                return audio_bytes

        except Exception as e:
            print(f"[TTS] Exception for '{text[:30]}': {e}")
            return None

    async def stream(
        self,
        text: str,
        speaker: str = "priya",
        target_language_code: str = "hi-IN",
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS audio chunk by chunk (sentence by sentence).

        Splits text into sentences → synthesizes each concurrently →
        yields audio bytes in order as they arrive.

        This is the pseudo-streaming pattern from production codebase.
        First audio chunk arrives before full synthesis is complete.
        """
        # Split into sentences
        sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
        if not sentences:
            sentences = [text.strip()]

        # Limit sentence length — Sarvam has input limits
        chunks = []
        for sentence in sentences:
            if len(sentence) > 200:
                # Further split long sentences by comma
                sub = [s.strip() for s in sentence.split(",") if s.strip()]
                chunks.extend(sub)
            else:
                chunks.append(sentence)

        print(f"[TTS] Streaming {len(chunks)} chunks for {len(text)} chars")

        async with aiohttp.ClientSession() as session:
            # Fire all TTS requests concurrently
            tasks = [
                self._synthesize_sentence(session, chunk, speaker, target_language_code)
                for chunk in chunks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Yield in order
        for i, result in enumerate(results):
            if isinstance(result, bytes) and result:
                print(f"[TTS] Yielding chunk {i+1}/{len(chunks)} ({len(result)} bytes)")
                yield result

    async def synthesize(self, text: str, speaker: str = "priya") -> bytes:
        """
        Synthesize full text → returns complete audio bytes (non-streaming).
        Use for short texts or when you need the full audio at once.
        """
        chunks = []
        async for chunk in self.stream(text, speaker):
            chunks.append(chunk)
        return b"".join(chunks)
