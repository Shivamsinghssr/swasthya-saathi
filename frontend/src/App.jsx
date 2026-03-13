import { useState } from 'react'
import Header from './components/Header'
import ChatTab from './components/ChatTab'
import VoiceTab from './components/VoiceTab'
import PrescriptionTab from './components/PrescriptionTab'
import styles from './App.module.css'

const TABS = [
  { id: 'chat',         label: 'Chat',         icon: '💬' },
  { id: 'voice',        label: 'Awaaz',         icon: '🎤' },
  { id: 'prescription', label: 'Prescription',  icon: '📋' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div className={styles.app}>
      <Header />

      <div className={styles.layout}>
        {/* Tab bar */}
        <nav className={styles.tabBar}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`${styles.tab} ${activeTab === t.id ? styles.active : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              <span className={styles.tabIcon}>{t.icon}</span>
              <span className={styles.tabLabel}>{t.label}</span>
            </button>
          ))}
        </nav>

        {/* Tab content */}
        <main className={styles.content}>
          {activeTab === 'chat'         && <ChatTab />}
          {activeTab === 'voice'        && <VoiceTab />}
          {activeTab === 'prescription' && <PrescriptionTab />}
        </main>
      </div>

      <footer className={styles.footer}>
        ⚠️ Yeh sirf jaankari ke liye hai — doctor ki jagah nahi.
        Emergency mein <strong>108</strong> dial karein.
      </footer>
    </div>
  )
}
