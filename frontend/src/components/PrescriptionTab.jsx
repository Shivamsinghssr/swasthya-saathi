import { useState, useRef } from 'react'
import { analyzePrescription } from '../api'
import MessageBubble from './MessageBubble'
import styles from './PrescriptionTab.module.css'

export default function PrescriptionTab() {
  const [preview, setPreview]   = useState(null)   // base64 data URL
  const [base64, setBase64]     = useState(null)   // raw base64
  const [mimeType, setMimeType] = useState('image/jpeg')
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const fileRef   = useRef(null)
  const cameraRef = useRef(null)

  function handleFile(file) {
    if (!file) return
    setResult(null); setError(null)
    setMimeType(file.type || 'image/jpeg')
    const reader = new FileReader()
    reader.onload = e => {
      const dataUrl = e.target.result
      setPreview(dataUrl)
      setBase64(dataUrl.split(',')[1])  // strip "data:image/jpeg;base64,"
    }
    reader.readAsDataURL(file)
  }

  async function analyze() {
    if (!base64) return
    setLoading(true); setError(null); setResult(null)
    try {
      const data = await analyzePrescription(base64, mimeType)
      setResult(data)
    } catch (e) {
      setError('Prescription read nahi ho saka. Dobara try karein.')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setPreview(null); setBase64(null)
    setResult(null);  setError(null)
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Prescription Padhen</h2>
        <p className={styles.subtitle}>Photo upload karein ya camera se lein</p>
      </div>

      {!preview ? (
        <div className={styles.uploadArea}>
          {/* File upload */}
          <button
            className={styles.uploadBtn}
            onClick={() => fileRef.current.click()}
          >
            <span className={styles.uploadIcon}>📁</span>
            <span>Gallery se upload karein</span>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />

          <div className={styles.divider}>ya</div>

          {/* Camera capture */}
          <button
            className={styles.uploadBtn}
            onClick={() => cameraRef.current.click()}
          >
            <span className={styles.uploadIcon}>📷</span>
            <span>Camera se photo lein</span>
          </button>
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
        </div>
      ) : (
        <div className={styles.previewSection}>
          <div className={styles.imageWrapper}>
            <img src={preview} alt="Prescription" className={styles.image} />
            <button className={styles.resetBtn} onClick={reset} title="Hatao">✕</button>
          </div>

          {!result && !loading && (
            <button className={styles.analyzeBtn} onClick={analyze}>
              🔍 Prescription Padhein
            </button>
          )}

          {loading && (
            <div className={styles.loadingRow}>
              <span className={styles.spinner} />
              <span>Prescription padh raha hoon...</span>
            </div>
          )}

          {error && <p className={styles.error}>{error}</p>}

          {result && (
            <div className={styles.result}>
              <MessageBubble
                role="bot"
                text={result.response}
                tools={result.tools_used || []}
              />
              <button className={styles.resetBtn2} onClick={reset}>
                Nayi Prescription
              </button>
            </div>
          )}
        </div>
      )}

      <p className={styles.note}>
        📝 Prescription ki photo clear aur seedhi rakhen. Dhundhli photo sahi se nahi padhi jaayegi.
      </p>
    </div>
  )
}
