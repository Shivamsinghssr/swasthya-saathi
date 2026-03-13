/**
 * api/index.js
 * All backend communication in one place.
 * Backend URL auto-detects: dev uses Vite proxy, prod uses same origin.
 */

const BASE = import.meta.env.DEV ? '' : ''  // Vite proxy handles /chat → localhost:8000

// ── Text Chat ─────────────────────────────────────────────────────────────────
export async function sendMessage(message, sessionId = 'web') {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`Chat error: ${res.status}`)
  return res.json()
  // Returns: { response, tools_used, session_id }
}

// ── Prescription Image ────────────────────────────────────────────────────────
export async function analyzePrescription(imageBase64, mimeType = 'image/jpeg') {
  const res = await fetch('/chat/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      mime_type: mimeType,
      session_id: 'web',
    }),
  })
  if (!res.ok) throw new Error(`Image error: ${res.status}`)
  return res.json()
  // Returns: { response, tools_used, session_id }
}

// ── Health Check ──────────────────────────────────────────────────────────────
export async function checkHealth() {
  const res = await fetch('/health')
  return res.json()
}

// ── WebSocket Voice ───────────────────────────────────────────────────────────
export function createVoiceWebSocket(handlers) {
  /**
   * handlers: {
   *   onTranscript(text),
   *   onResponseText(text),
   *   onAudioChunk(arrayBuffer),
   *   onAudioStart(),
   *   onAudioEnd(),
   *   onError(message),
   *   onOpen(),
   *   onClose(),
   * }
   */
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${protocol}://${location.host}/ws/voice`)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    handlers.onOpen?.()
    // Keepalive ping every 20s
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 20000)
    ws._pingInterval = interval
  }

  ws.onclose = () => {
    clearInterval(ws._pingInterval)
    handlers.onClose?.()
  }

  ws.onerror = () => handlers.onError?.('WebSocket connection failed')

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      handlers.onAudioChunk?.(event.data)
      return
    }
    try {
      const msg = JSON.parse(event.data)
      switch (msg.type) {
        case 'transcript':    handlers.onTranscript?.(msg.text);    break
        case 'response_text': handlers.onResponseText?.(msg.text);  break
        case 'audio_start':   handlers.onAudioStart?.();            break
        case 'audio_end':     handlers.onAudioEnd?.();              break
        case 'error':         handlers.onError?.(msg.message);      break
      }
    } catch { /* pong or unknown */ }
  }

  return ws
}
