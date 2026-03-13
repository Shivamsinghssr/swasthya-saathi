"""
voice/voice_runner.py

Thin orchestration layer connecting STT → Agent → TTS.

This is the ONLY new file that touches the agent.
It calls get_graph().invoke() — the exact same call main.py makes.
Voice is just a different I/O layer on top of the same Phase 1 agent.

Flow:
    audio_bytes → SarvamSTT → transcript
    transcript  → LangGraph agent → response_text
    response_text → SarvamTTS → audio_chunks (streamed)
"""
import asyncio
from typing import AsyncGenerator, Callable, Optional

from langchain_core.messages import HumanMessage

from agent.graph import get_graph
from voice.stt.sarvam_stt import SarvamSTT
from voice.tts.sarvam_tts import SarvamTTS


class VoiceRunner:
    """
    Orchestrates the full voice pipeline:
    Audio in → STT → Agent → TTS → Audio out

    Designed to be used per-WebSocket connection.
    Stateless — no session state stored here.
    """

    def __init__(self, sarvam_api_key: str):
        self.stt = SarvamSTT(api_key=sarvam_api_key)
        self.tts = SarvamTTS(api_key=sarvam_api_key)
        self.graph = get_graph()

    async def process(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        on_transcript: Optional[Callable[[str], None]] = None,
        on_response_text: Optional[Callable[[str], None]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Full pipeline: audio → transcript → agent → audio stream.

        Args:
            audio_bytes:      Raw audio from browser WebSocket
            mime_type:        Audio MIME type (audio/webm from Chrome)
            on_transcript:    Callback fired when STT returns (for UI display)
            on_response_text: Callback fired when agent returns text (for UI display)

        Yields:
            Audio bytes chunks (WAV) to stream back to browser
        """
        # ── Step 1: STT ────────────────────────────────────────────────────────
        print(f"[VoiceRunner] STT: {len(audio_bytes)} bytes audio")
        stt_result = await self.stt.transcribe(audio_bytes, mime_type)

        if not stt_result["success"] or not stt_result["transcript"]:
            print("[VoiceRunner] STT failed or empty transcript")
            # Yield a short error audio response
            error_text = "Kshama karein, aapki awaaz clearly nahi aayi. Dobara bolein."
            async for chunk in self.tts.stream(error_text):
                yield chunk
            return

        transcript = stt_result["transcript"]
        print(f"[VoiceRunner] Transcript: {transcript}")

        # Fire transcript callback (WebSocket sends this to browser for display)
        if on_transcript:
            on_transcript(transcript)

        # ── Step 2: Agent ──────────────────────────────────────────────────────
        print(f"[VoiceRunner] Running agent for: {transcript[:60]}")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.graph.invoke(
                {"messages": [HumanMessage(content=transcript)]}
            ),
        )

        # Extract final text response
        final_message = result["messages"][-1]
        response_text = (
            final_message.content
            if isinstance(final_message.content, str)
            else str(final_message.content)
        )

        # Remove the safety disclaimer from TTS (too long to speak)
        # Keep it in text display but don't speak it
        tts_text = response_text.split("⚠️")[0].strip()
        if not tts_text:
            tts_text = response_text

        print(f"[VoiceRunner] Agent response ({len(response_text)} chars)")

        # Fire response text callback
        if on_response_text:
            on_response_text(response_text)

        # ── Step 3: TTS ────────────────────────────────────────────────────────
        print(f"[VoiceRunner] TTS streaming...")
        async for audio_chunk in self.tts.stream(tts_text):
            yield audio_chunk

        print(f"[VoiceRunner] Done.")
