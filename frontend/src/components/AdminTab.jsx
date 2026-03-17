import { useState, useEffect, useCallback } from 'react'
import styles from './AdminTab.module.css'

const API = '/admin'

// ── API helpers ────────────────────────────────────────────────────────────────
async function adminFetch(path, token, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (res.status === 401) throw new Error('Invalid password')
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({ label, value, unit = '', color = 'var(--accent)' }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statValue} style={{ color }}>{value}</div>
      {unit && <div className={styles.statUnit}>{unit}</div>}
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}

function ToolBar({ tool, count, total }) {
  const pct = total > 0 ? Math.round(count / total * 100) : 0
  return (
    <div className={styles.toolBar}>
      <div className={styles.toolName}>{tool}</div>
      <div className={styles.toolTrack}>
        <div className={styles.toolFill} style={{ width: `${pct}%` }} />
      </div>
      <div className={styles.toolCount}>{count} ({pct}%)</div>
    </div>
  )
}

function LogRow({ log }) {
  const time = new Date(log.timestamp).toLocaleTimeString('en-IN')
  const date = new Date(log.timestamp).toLocaleDateString('en-IN')
  return (
    <div className={styles.logRow}>
      <div className={styles.logTime}>{date} {time}</div>
      <div className={styles.logQuery}>{log.query}</div>
      <div className={styles.logTools}>
        {(log.tools_used || []).map(t => (
          <span key={t} className={styles.toolBadge}>{t}</span>
        ))}
      </div>
      <div className={styles.logLatency}>{log.latency_s}s</div>
      <div className={`${styles.logStatus} ${log.success ? styles.ok : styles.fail}`}>
        {log.success ? '✓' : '✗'}
      </div>
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function AdminTab() {
  const [token, setToken]         = useState('')
  const [input, setInput]         = useState('')
  const [authed, setAuthed]       = useState(false)
  const [authError, setAuthError] = useState('')
  const [loading, setLoading]     = useState(false)
  const [tab, setTab]             = useState('overview')

  const [stats, setStats]         = useState(null)
  const [evalData, setEvalData]   = useState(null)
  const [evalRunning, setEvalRunning] = useState(false)
  const [sysHealth, setSysHealth] = useState(null)

  const load = useCallback(async (t) => {
    setLoading(true)
    try {
      const [s, e, h] = await Promise.all([
        adminFetch('/stats', t),
        adminFetch('/eval/latest', t),
        adminFetch('/system', t),
      ])
      setStats(s)
      setEvalData(e)
      setSysHealth(h)
    } catch (err) {
      if (err.message === 'Invalid password') {
        setAuthed(false)
        setAuthError('Session expired')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  async function login() {
    setAuthError('')
    try {
      await adminFetch('/system', input)
      setToken(input)
      setAuthed(true)
      load(input)
    } catch {
      setAuthError('Incorrect password')
    }
  }

  async function runEval() {
    setEvalRunning(true)
    try {
      await adminFetch('/eval/run', token, { method: 'POST' })
      setTimeout(() => {
        adminFetch('/eval/latest', token).then(e => {
          setEvalData(e)
          setEvalRunning(false)
        })
      }, 120000)  // check after 2 minutes
    } catch {
      setEvalRunning(false)
    }
  }

  // ── Login screen ─────────────────────────────────────────────────────────────
  if (!authed) {
    return (
      <div className={styles.loginWrap}>
        <div className={styles.loginCard}>
          <div className={styles.loginIcon}>🔐</div>
          <h2 className={styles.loginTitle}>Admin Dashboard</h2>
          <p className={styles.loginSub}>Enter admin password to continue</p>
          <input
            className={styles.loginInput}
            type="password"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && login()}
            placeholder="Admin password"
            autoFocus
          />
          {authError && <p className={styles.loginError}>{authError}</p>}
          <button className={styles.loginBtn} onClick={login}>
            Login
          </button>
        </div>
      </div>
    )
  }

  // ── Dashboard ─────────────────────────────────────────────────────────────────
  const totalTools = stats
    ? Object.values(stats.tool_counts || {}).reduce((a, b) => a + b, 0)
    : 0

  return (
    <div className={styles.dashboard}>

      {/* Tab Nav */}
      <div className={styles.tabNav}>
        {['overview', 'logs', 'eval', 'system'].map(t => (
          <button
            key={t}
            className={`${styles.navBtn} ${tab === t ? styles.navActive : ''}`}
            onClick={() => { setTab(t); load(token) }}
          >
            {t === 'overview' && '📊'}
            {t === 'logs'     && '📋'}
            {t === 'eval'     && '🧪'}
            {t === 'system'   && '⚙️'}
            {' '}{t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
        <button className={styles.refreshBtn} onClick={() => load(token)} disabled={loading}>
          {loading ? '...' : '↻'}
        </button>
      </div>

      {/* Overview */}
      {tab === 'overview' && stats && (
        <div className={styles.panel}>
          <div className={styles.statsGrid}>
            <StatCard label="Total Queries"   value={stats.total_queries}  color="var(--accent)" />
            <StatCard label="Avg Latency"     value={stats.avg_latency_s} unit="s" color="var(--accent-2)" />
            <StatCard label="Success Rate"    value={`${stats.success_rate}%`} color="#22c55e" />
            <StatCard label="Top Tool"        value={stats.top_tool || '—'} color="#a855f7" />
          </div>

          <h3 className={styles.sectionTitle}>Tool Usage</h3>
          <div className={styles.toolList}>
            {Object.entries(stats.tool_counts || {})
              .sort(([,a],[,b]) => b - a)
              .map(([tool, count]) => (
                <ToolBar key={tool} tool={tool} count={count} total={totalTools} />
              ))
            }
            {totalTools === 0 && (
              <p className={styles.empty}>No tool calls logged yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Logs */}
      {tab === 'logs' && stats && (
        <div className={styles.panel}>
          <h3 className={styles.sectionTitle}>Recent Queries ({stats.recent_logs?.length || 0})</h3>
          <div className={styles.logHeader}>
            <span>Time</span>
            <span>Query</span>
            <span>Tools</span>
            <span>Latency</span>
            <span>✓</span>
          </div>
          <div className={styles.logList}>
            {(stats.recent_logs || []).map((log, i) => (
              <LogRow key={i} log={log} />
            ))}
            {(!stats.recent_logs || stats.recent_logs.length === 0) && (
              <p className={styles.empty}>No queries logged yet. Ask something first!</p>
            )}
          </div>
        </div>
      )}

      {/* Eval */}
      {tab === 'eval' && (
        <div className={styles.panel}>
          <div className={styles.evalHeader}>
            <h3 className={styles.sectionTitle}>Evaluation Harness</h3>
            <button
              className={styles.runEvalBtn}
              onClick={runEval}
              disabled={evalRunning}
            >
              {evalRunning ? '⏳ Running (~2 min)...' : '▶ Run Eval'}
            </button>
          </div>

          {evalData?.results ? (
            <>
              <div className={styles.statsGrid}>
                <StatCard label="Pass Rate"    value={evalData.results.pass_rate}    color="#22c55e" />
                <StatCard label="Total Tests"  value={evalData.results.total}        color="var(--accent)" />
                <StatCard label="Failed"       value={evalData.results.failed}       color="#ef4444" />
                <StatCard label="Avg Latency"  value={`${evalData.results.avg_latency_s}s`} color="var(--accent-2)" />
              </div>

              <h3 className={styles.sectionTitle}>Test Results</h3>
              <div className={styles.evalList}>
                {(evalData.results.results || []).map(r => (
                  <div key={r.id} className={`${styles.evalRow} ${r.passed ? styles.evalPass : styles.evalFail}`}>
                    <span className={styles.evalId}>{r.id}</span>
                    <span className={styles.evalDesc}>{r.description}</span>
                    <span className={styles.evalTools}>{(r.tools_called || []).join(', ')}</span>
                    <span className={styles.evalTime}>{r.latency_s}s</span>
                    <span className={styles.evalStatus}>{r.passed ? '✅' : '❌'}</span>
                  </div>
                ))}
              </div>

              <p className={styles.evalFile}>
                📁 File: {evalData.file}
              </p>
            </>
          ) : (
            <div className={styles.evalEmpty}>
              <p>No eval results yet.</p>
              <p className={styles.evalHint}>
                Click "Run Eval" to test all 15 golden test cases.<br/>
                Note: Uses Groq API — takes ~2 minutes.
              </p>
            </div>
          )}
        </div>
      )}

      {/* System */}
      {tab === 'system' && sysHealth && (
        <div className={styles.panel}>
          <h3 className={styles.sectionTitle}>System Health</h3>
          <div className={styles.healthGrid}>
            {[
              ['Session Store', sysHealth.session_store_backend === 'redis' ? '✅ Redis' : '⚠️ Memory'],
              ['Query Logger',  sysHealth.query_logger_backend  === 'redis' ? '✅ Redis' : '⚠️ Memory'],
              ['FAISS Indexes', sysHealth.indexes_built ? '✅ Built' : '❌ Missing'],
              ['Admin Password', sysHealth.admin_password_set ? '✅ Set' : '❌ Not set'],
              ['Groq API Key',   sysHealth.groq_key_set   ? '✅ Set' : '❌ Not set'],
              ['Sarvam API Key', sysHealth.sarvam_key_set ? '✅ Set' : '❌ Not set'],
              ['Redis URL',      sysHealth.redis_url_set  ? '✅ Set' : '⚠️ Not set (using memory)'],
              ['Total Queries Logged', sysHealth.total_queries_logged],
            ].map(([k, v]) => (
              <div key={k} className={styles.healthRow}>
                <span className={styles.healthKey}>{k}</span>
                <span className={styles.healthVal}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
