import styles from './MessageBubble.module.css'

export default function MessageBubble({ role, text, tools = [] }) {
  const isUser = role === 'user'

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.userWrapper : styles.botWrapper} fade-up`}>
      <div className={`${styles.bubble} ${isUser ? styles.user : styles.bot}`}>
        <div className={styles.label}>
          {isUser ? 'Aap' : '🏥 Swasthya Saathi'}
        </div>
        <p className={`${styles.text} ${!isUser ? 'hindi' : ''}`}>
          {text}
        </p>
        {tools.length > 0 && (
          <div className={styles.tools}>
            {tools.map(t => (
              <span key={t} className={styles.badge}>🔧 {t}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
