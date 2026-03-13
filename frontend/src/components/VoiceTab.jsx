import { useState, useRef, useEffect, useCallback } from 'react'
import { createVoiceWebSocket } from '../api'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import MessageBubble from './MessageBubble'
import styles from './VoiceTab.module.css'

const STATUS = {
  CONNECTING: 'connecting',
  READY:      'ready',
  RECORDING:  'recording',
  PROCESSING: 'processing',
  SPEAKING:   'speaking',
  ERROR:      'error',
}

const STATUS_LABELS = {
  [STATUS.CONNECTING]:  'Jud raha hai...',
  [STATUS.READY]:       'Mic dabayein aur bolein',
  [STATUS.RECORDING]:   'Sun raha hoon... (rokne ke liye dobara dabayein)',
  [STATUS.PROCESSING]:  'Soch raha hoon...',
  [STATUS.SPEAKING]:    'Bol raha hoon...',
  [STATUS.ERROR]:       'Connection toot gayi — refresh karein',
}

export default function VoiceTab() {
  const [status, setStatus]     = useState(STATUS.CONNECTING)
  const [messages, setMessages] = useState([])
  const wsRef           = useRef(null)
  const mediaRecRef     = useRef(null)
  const chunksRef       = useRef([])
  const bottomRef       = useRef(null)
  const { enqueue, clear } = useAudioPlayer()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Connect WebSocket on mount
  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [])

  function connect() {
    setStatus(STATUS.CONNECTING)
    wsRef.current = createVoiceWebSocket({
      onOpen:         ()  => setStatus(STATUS.READY),
      onClose:        ()  => setStatus(STATUS.ERROR),
      onError:        ()  => setStatus(STATUS.ERROR),
      onTranscript:   (t) => {
        setMessages(m => [...m, { role: 'user', text: t, tools: [] }])
        setStatus(STATUS.PROCESSING)
      },
      onResponseText: (t) => {
        setMessages(m => [...m, { role: 'bot', text: t, tools: [] }])
      },
      onAudioStart:   ()  => { clear(); setStatus(STATUS.SPEAKING) },
      onAudioEnd:     ()  => setStatus(STATUS.READY),
      onAudioChunk:   (b) => enqueue(b),
    })
  }

  async function toggleRecording() {
    if (status === STATUS.RECORDING) {
      stopRecording()
    } else if (status === STATUS.READY) {
      await startRecording()
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const buf  = await blob.arrayBuffer()
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(buf)
          setStatus(STATUS.PROCESSING)
        }
        stream.getTracks().forEach(t => t.stop())
      }
      rec.start()
      mediaRecRef.current = rec
      setStatus(STATUS.RECORDING)
    } catch {
      setStatus(STATUS.ERROR)
    }
  }

  function stopRecording() {
    mediaRecRef.current?.stop()
  }

  const btnClass = [
    styles.micBtn,
    status === STATUS.RECORDING  ? styles.recording  : '',
    status === STATUS.SPEAKING   ? styles.speaking   : '',
    status === STATUS.PROCESSING ? styles.processing : '',
  ].filter(Boolean).join(' ')

  const canRecord = status === STATUS.READY || status === STATUS.RECORDING

  return (
    <div className={styles.container}>
      <div className={styles.micSection}>
        <button
          className={btnClass}
          onClick={toggleRecording}
          disabled={!canRecord}
          aria-label="Mic toggle"
        >
          {status === STATUS.PROCESSING
            ? <span className={styles.spinner} />
            : status === STATUS.RECORDING
            ? '⏹'
            : '🎤'
          }
        </button>
        <p className={`${styles.statusText} ${status === STATUS.ERROR ? styles.error : ''}`}>
          {STATUS_LABELS[status]}
        </p>
      </div>

      <div className={styles.messages}>
        {messages.length === 0 && (
          <p className={styles.hint}>Awaaz mein sawaal poochhen — Hindi mein</p>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} text={m.text} tools={m.tools} />
        ))}
        <div ref={bottomRef} />
      </div>

      <p className={styles.disclaimer}>
        ⚠️ Emergency mein <strong>108</strong> dial karein
      </p>
    </div>
  )
}
