"""
api/voice.py

WebSocket endpoint for real-time voice interaction.

Protocol:
    Client → Server:
        1. Binary message: raw audio bytes (WebM from Chrome MediaRecorder)

    Server → Client:
        1. Text message: {"type": "transcript", "text": "mujhe bukhar hai"}
        2. Text message: {"type": "response_text", "text": "Bukhar ke liye..."}
        3. Text message: {"type": "audio_start"}
        4. Binary messages: WAV audio chunks (stream)
        5. Text message: {"type": "audio_end"}
        6. Text message: {"type": "error", "message": "..."}  (on failure)

Usage:
    ws = new WebSocket("ws://localhost:8000/ws/voice")
    ws.send(audioBlob)       // send recorded audio
    ws.onmessage = handler   // receive transcript + audio
"""
import json
import os
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from voice.voice_runner import VoiceRunner


router = APIRouter()

# Singleton runner — initialized once, reused across connections
_voice_runner: VoiceRunner = None


def init_voice_runner():
    """Called once at server startup after tools are initialized."""
    global _voice_runner
    api_key = os.getenv("SARVAM_API_KEY", "")
    if not api_key:
        print("⚠️  [Voice] SARVAM_API_KEY not set — voice endpoint disabled.")
        return
    _voice_runner = VoiceRunner(sarvam_api_key=api_key)
    print("[Voice] ✅ VoiceRunner ready.")


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice.

    Accepts audio bytes, streams back transcript + TTS audio.
    Each message = one complete utterance (recorded until user stops).
    """
    await websocket.accept()
    print(f"[Voice WS] Client connected: {websocket.client}")

    if not _voice_runner:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Voice service not initialized. Check SARVAM_API_KEY."
        }))
        await websocket.close()
        return

    try:
        while True:
            # Wait for audio bytes from browser
            message = await websocket.receive()

            # Handle binary audio data
            if "bytes" in message and message["bytes"]:
                audio_bytes = message["bytes"]
                print(f"[Voice WS] Received {len(audio_bytes)} bytes audio")

                # Callbacks to send intermediate updates to browser
                async def send_transcript(text: str):
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": text,
                    }))

                async def send_response_text(text: str):
                    await websocket.send_text(json.dumps({
                        "type": "response_text",
                        "text": text,
                    }))

                # Notify browser: audio is starting
                await websocket.send_text(json.dumps({"type": "audio_start"}))

                # Run full pipeline: STT → Agent → TTS stream
                async for audio_chunk in _voice_runner.process(
                    audio_bytes=audio_bytes,
                    mime_type="audio/webm",
                    on_transcript=lambda t: asyncio.ensure_future(
                    websocket.send_text(json.dumps({"type": "transcript", "text": t}))
                ),
                on_response_text=lambda r: asyncio.ensure_future(
                    websocket.send_text(json.dumps({"type": "response_text", "text": r}))
                ),
                ):
                    # Stream audio chunks to browser
                    await websocket.send_bytes(audio_chunk)

                # Notify browser: audio stream complete
                await websocket.send_text(json.dumps({"type": "audio_end"}))

            # Handle text ping (keepalive)
            elif "text" in message:
                data = message["text"]
                if data == "ping":
                    await websocket.send_text("pong")

    except WebSocketDisconnect:
        print(f"[Voice WS] Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"[Voice WS] Error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:
            pass
