import { useRef, useCallback } from 'react'

/**
 * useAudioPlayer
 * Plays a queue of WAV ArrayBuffers in order using Web Audio API.
 * Same chunked playback pattern as Phase 2 HTML but as a reusable hook.
 */
export function useAudioPlayer() {
  const queue = useRef([])
  const playing = useRef(false)

  const playNext = useCallback(async () => {
    if (queue.current.length === 0) { playing.current = false; return }
    playing.current = true
    const chunk = queue.current.shift()
    try {
      const ctx = new AudioContext({ sampleRate: 16000 })
      const buffer = await ctx.decodeAudioData(chunk.slice(0))
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)
      source.onended = () => { ctx.close(); playNext() }
      source.start(0)
    } catch (e) {
      console.warn('[AudioPlayer] decode error:', e)
      playNext()
    }
  }, [])

  const enqueue = useCallback((arrayBuffer) => {
    queue.current.push(arrayBuffer)
    if (!playing.current) playNext()
  }, [playNext])

  const clear = useCallback(() => {
    queue.current = []
    playing.current = false
  }, [])

  return { enqueue, clear }
}
