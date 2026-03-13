import { useTheme } from '../hooks/useTheme'
import styles from './Header.module.css'

export default function Header() {
  const { theme, toggle } = useTheme()

  return (
    <header className={styles.header}>
      <div className={styles.logo}>
        <span className={styles.icon}>🏥</span>
        <div>
          <h1 className={styles.title}>Swasthya Saathi</h1>
          <p className={styles.subtitle} lang="hi">स्वास्थ्य साथी</p>
        </div>
      </div>

      <div className={styles.right}>
        <span className={styles.tagline}>Rural UP & Bihar • Hindi Health Agent</span>
        <button
          className={styles.themeBtn}
          onClick={toggle}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </div>
    </header>
  )
}
