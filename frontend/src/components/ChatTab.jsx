import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../api'
import MessageBubble from './MessageBubble'
import styles from './ChatTab.module.css'

const SUGGESTIONS = [
  'मुझे बुखार है',
  'Paracetamol kaise lein?',
  'Ayushman Bharat kya hai?',
  'Varanasi mein PHC kahan hai?',
]

export default function ChatTab() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(text) {
    const msg = text || input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', text: msg, tools: [] }])
    setLoading(true)
    try {
      const data = await sendMessage(msg)
      setMessages(m => [...m, {
        role: 'bot',
        text: data.response,
        tools: data.tools_used || [],
      }])
    } catch (e) {
      setMessages(m => [...m, {
        role: 'bot',
        text: 'Khed hai, kuch galat ho gaya. Dobara try karein.',
        tools: [],
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      {messages.length === 0 && (
        <div className={styles.empty}>
          <p className={`${styles.emptyTitle} hindi`}>नमस्ते! मैं आपका स्वास्थ्य साथी हूँ।</p>
          <p className={styles.emptySubtitle}>Kuch poochhen — Hindi mein bolein ya type karein</p>
          <div className={styles.suggestions}>
            {SUGGESTIONS.map(s => (
              <button key={s} className={styles.suggestion} onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={styles.messages}>
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} text={m.text} tools={m.tools} />
        ))}
        {loading && (
          <div className={styles.typing}>
            <span /><span /><span />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className={styles.inputRow}>
        <input
          className={styles.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Hindi mein type karein..."
          disabled={loading}
        />
        <button
          className={styles.sendBtn}
          onClick={() => send()}
          disabled={loading || !input.trim()}
        >
          {loading ? <span className={styles.spinner} /> : '↑'}
        </button>
      </div>
    </div>
  )
}
