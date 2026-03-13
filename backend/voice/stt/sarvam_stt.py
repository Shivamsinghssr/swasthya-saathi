"""
voice/stt/sarvam_stt.py

Sarvam AI Speech-to-Text.
Accepts raw audio bytes, returns transcript.

Sarvam STT API:
  POST https://api.sarvam.ai/speech-to-text
  - Supports Hindi + English auto-detection
  - Accepts WAV/WebM audio
  - Returns transcript with language detected
"""
import asyncio
import aiohttp
import io
import os
from typing import Optional


SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT:
    """
    Sarvam Speech-to-Text client.
    
    Usage:
        stt = SarvamSTT(api_key="sk-...")
        transcript = await stt.transcribe(audio_bytes, mime_type="audio/webm")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not set")

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        language_code: str = "unknown",  # unknown = auto-detect
    ) -> dict:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data from browser (WebM/WAV)
            mime_type:   MIME type of audio — "audio/webm" from Chrome MediaRecorder
            language_code: "unknown" for auto-detect, "hi-IN" to force Hindi

        Returns:
            {
                "transcript": "mujhe bukhar hai",
                "language_code": "hi-IN",
                "success": True
            }
        """
        if not audio_bytes:
            return {"transcript": "", "language_code": "hi-IN", "success": False}

        headers = {
            "api-subscription-key": self.api_key,
        }

        # Determine file extension from mime type
        ext = "webm" if "webm" in mime_type else "wav"
        filename = f"audio.{ext}"

        form = aiohttp.FormData()
        form.add_field(
            "file",
            io.BytesIO(audio_bytes),
            filename=filename,
            content_type=mime_type,
        )
        form.add_field("language_code", language_code)
        form.add_field("model", "saarika:v2.5")      # Sarvam's latest STT model

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SARVAM_STT_URL,
                    headers=headers,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"[STT] Error {resp.status}: {error_text}")
                        return {
                            "transcript": "",
                            "language_code": "hi-IN",
                            "success": False,
                            "error": error_text,
                        }

                    data = await resp.json()
                    transcript = data.get("transcript", "").strip()
                    lang = data.get("language_code", "hi-IN")

                    print(f"[STT] Transcript ({lang}): {transcript[:80]}")
                    return {
                        "transcript": transcript,
                        "language_code": lang,
                        "success": True,
                    }

        except asyncio.TimeoutError:
            print("[STT] Timeout — audio too long or network slow")
            return {"transcript": "", "language_code": "hi-IN", "success": False, "error": "timeout"}

        except Exception as e:
            print(f"[STT] Exception: {e}")
            return {"transcript": "", "language_code": "hi-IN", "success": False, "error": str(e)}
