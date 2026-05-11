import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { sendMessage, getHealth } from './lib/api.js'

const SUGGESTED_QUERIES = [
  "Is the ML Platform team over budget this quarter?",
  "Detect spend anomalies in the data-pipeline service",
  "What is the rightsizing recommendation for ml-training?",
  "What is the policy for budget exceptions over $5,000?",
  "Get the current benchmark for cloud infrastructure costs",
  "Analyze storage service spend and flag any issues",
]

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function StatusBadge({ status, label }) {
  const color = status === 'ok' || status === 'ready' || status === true
    ? '#22c55e' : status === 'degraded' ? '#f59e0b' : '#ef4444'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block' }} />
      {label}
    </span>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start', marginBottom: 20,
    }}>
      <div style={{
        maxWidth: '82%', background: isUser ? '#1e40af' : '#1e293b',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        padding: '12px 16px', border: `1px solid ${isUser ? '#2563eb' : '#334155'}`,
      }}>
        {isUser ? (
          <p style={{ color: '#e2e8f0', fontSize: 14, lineHeight: 1.6 }}>{msg.content}</p>
        ) : (
          <div style={{ color: '#e2e8f0', fontSize: 14, lineHeight: 1.7 }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div style={{ overflowX: 'auto', margin: '8px 0' }}>
                    <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th style={{ border: '1px solid #475569', padding: '6px 10px', background: '#0f172a', textAlign: 'left', color: '#94a3b8' }}>{children}</th>
                ),
                td: ({ children }) => (
                  <td style={{ border: '1px solid #334155', padding: '6px 10px' }}>{children}</td>
                ),
                code: ({ inline, children }) => inline
                  ? <code style={{ background: '#0f172a', padding: '2px 6px', borderRadius: 4, fontSize: 12, color: '#7dd3fc' }}>{children}</code>
                  : <pre style={{ background: '#0f172a', padding: 12, borderRadius: 8, overflowX: 'auto', fontSize: 12, border: '1px solid #334155' }}><code style={{ color: '#7dd3fc' }}>{children}</code></pre>,
                p: ({ children }) => <p style={{ marginBottom: 8 }}>{children}</p>,
                ul: ({ children }) => <ul style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
                strong: ({ children }) => <strong style={{ color: '#93c5fd' }}>{children}</strong>,
                h1: ({ children }) => <h1 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: '#f1f5f9' }}>{children}</h1>,
                h2: ({ children }) => <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 6, color: '#f1f5f9' }}>{children}</h2>,
                h3: ({ children }) => <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, color: '#cbd5e1' }}>{children}</h3>,
                blockquote: ({ children }) => (
                  <blockquote style={{ borderLeft: '3px solid #3b82f6', paddingLeft: 12, marginLeft: 0, color: '#94a3b8', fontStyle: 'italic' }}>{children}</blockquote>
                ),
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4, padding: '0 4px' }}>
        <span style={{ fontSize: 11, color: '#475569' }}>{formatTime(msg.timestamp)}</span>
        {!isUser && msg.meta && (
          <>
            {msg.meta.rag_context_used && (
              <span style={{ fontSize: 11, color: '#6366f1', background: '#1e1b4b', padding: '1px 6px', borderRadius: 10, border: '1px solid #312e81' }}>
                📚 RAG
              </span>
            )}
            {msg.meta.tool_calls_made?.length > 0 && (
              <span style={{ fontSize: 11, color: '#059669', background: '#052e16', padding: '1px 6px', borderRadius: 10, border: '1px solid #065f46' }}>
                🔧 {msg.meta.tool_calls_made.join(', ')}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 0', marginBottom: 16 }}>
      <div style={{ background: '#1e293b', borderRadius: '18px 18px 18px 4px', padding: '10px 16px', border: '1px solid #334155', display: 'flex', gap: 4, alignItems: 'center' }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: '50%', background: '#475569',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`, display: 'inline-block',
          }} />
        ))}
      </div>
      <span style={{ fontSize: 12, color: '#475569' }}>Analyzing with real market data...</span>
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([{
    id: 'welcome', role: 'assistant',
    content: `# FinOps Advisory Agent 💰\n\nI'm your AI-powered Cloud Financial Operations advisor. I combine:\n- **Live market data** \n- **Policy knowledge** (FinOps playbooks and budget policies)\n- **Statistical anomaly detection** (Z-score analysis)\n\nAsk me about budget overruns, anomalies, rightsizing, or FinOps policies.`,
    timestamp: new Date().toISOString(), meta: null,
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())
  const [health, setHealth] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => {
    getHealth().then(h => setHealth(h)).catch(() => setHealth({ status: 'error', ollama_reachable: false, vector_store_ready: false }))
  }, [])

  const handleSend = useCallback(async (text) => {
    const content = (text || input).trim()
    if (!content || loading) return
    setInput('')
    const userMsg = { id: crypto.randomUUID(), role: 'user', content, timestamp: new Date().toISOString(), meta: null }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    try {
      const data = await sendMessage(content, sessionId)
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'assistant', content: data.response,
        timestamp: data.timestamp,
        meta: { tool_calls_made: data.tool_calls_made, rag_context_used: data.rag_context_used },
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'assistant',
        content: `**Error:** ${err.message}\n\nPlease check that Ollama is running and the model is pulled.`,
        timestamp: new Date().toISOString(), meta: null,
      }])
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [input, loading, sessionId])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div style={{ display: 'flex', height: '100dvh', overflow: 'hidden', background: '#0f1117' }}>
      <style>{`
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        button { cursor: pointer; transition: opacity 0.15s; }
        button:disabled { opacity: 0.4; cursor: not-allowed; }
        textarea { resize: none; }
      `}</style>

      {/* Sidebar */}
      <div style={{ width: sidebarOpen ? 260 : 0, overflow: 'hidden', transition: 'width 0.25s ease', background: '#0d1117', borderRight: '1px solid #1e293b', flexShrink: 0 }}>
        <div style={{ padding: 16, minWidth: 260 }}>
          <h2 style={{ color: '#f1f5f9', fontSize: 14, fontWeight: 700, marginBottom: 16 }}>FinOps Agent</h2>
          {health && (
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 11, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Status</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <StatusBadge status={health.status} label={`API: ${health.status}`} />
                <StatusBadge status={health.ollama_reachable} label={`Ollama: ${health.ollama_reachable ? 'connected' : 'offline'}`} />
                <StatusBadge status={health.vector_store_ready} label={`Vector Store: ${health.vector_store_ready ? 'ready' : 'loading'}`} />
                {health.model && <span style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Model: {health.model}</span>}
              </div>
            </div>
          )}
          <p style={{ fontSize: 11, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>Suggested</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {SUGGESTED_QUERIES.map((q, i) => (
              <button key={i} onClick={() => { handleSend(q); if (window.innerWidth < 768) setSidebarOpen(false) }}
                disabled={loading}
                style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#94a3b8', fontSize: 12, padding: '7px 10px', textAlign: 'left' }}
                onMouseEnter={e => e.currentTarget.style.background = '#273548'}
                onMouseLeave={e => e.currentTarget.style.background = '#1e293b'}
              >{q}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Chat */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', background: '#0d1117', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <button onClick={() => setSidebarOpen(o => !o)} style={{ background: 'none', border: 'none', color: '#64748b', fontSize: 18, padding: 4 }}>☰</button>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>FinOps Advisory Agent</h1>
            <p style={{ fontSize: 11, color: '#475569' }}>Cloud Cost Intelligence • LangGraph + Qdrant + Ollama</p>
          </div>
          {health && <StatusBadge status={health.status} label={health.status === 'ok' ? 'Online' : 'Degraded'} />}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 0' }}>
          {messages.map(msg => <Message key={msg.id} msg={msg} />)}
          {loading && <TypingIndicator />}
          <div ref={messagesEndRef} style={{ height: 20 }} />
        </div>

        {messages.length <= 2 && !loading && (
          <div style={{ padding: '0 20px 8px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {SUGGESTED_QUERIES.slice(0, 3).map((q, i) => (
              <button key={i} onClick={() => handleSend(q)}
                style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 20, color: '#94a3b8', fontSize: 12, padding: '6px 12px' }}
                onMouseEnter={e => { e.currentTarget.style.background = '#273548'; e.currentTarget.style.color = '#e2e8f0' }}
                onMouseLeave={e => { e.currentTarget.style.background = '#1e293b'; e.currentTarget.style.color = '#94a3b8' }}
              >{q}</button>
            ))}
          </div>
        )}

        <div style={{ padding: '12px 16px', borderTop: '1px solid #1e293b', background: '#0d1117', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 8, background: '#1e293b', border: '1px solid #334155', borderRadius: 12, padding: '8px 12px' }}>
            <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
              placeholder="Ask about cloud costs, anomalies, budgets, or FinOps policies..." rows={2}
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: '#e2e8f0', fontSize: 14, lineHeight: 1.5, fontFamily: 'inherit', padding: 0 }}
            />
            <button onClick={() => handleSend()} disabled={loading || !input.trim()}
              style={{ background: loading || !input.trim() ? '#1e3a5f' : '#1e40af', border: 'none', borderRadius: 8, color: '#e2e8f0', width: 36, height: 36, fontSize: 16, alignSelf: 'flex-end', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >{loading ? '⏳' : '↑'}</button>
          </div>
          <p style={{ fontSize: 11, color: '#334155', textAlign: 'center', marginTop: 5 }}>Enter to send • Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  )
}
