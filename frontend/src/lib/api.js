const BASE = import.meta.env.VITE_API_URL || ''

export async function sendMessage(message, sessionId) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Server error' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getHealth() {
  const res = await fetch(`${BASE}/api/health`)
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function getIndexStatus() {
  const res = await fetch(`${BASE}/api/index/status`)
  if (!res.ok) throw new Error('Status check failed')
  return res.json()
}

export async function listDocuments() {
  const res = await fetch(`${BASE}/api/documents`)
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}
