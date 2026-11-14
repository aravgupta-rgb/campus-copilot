// Talks to the ADK agent server (adk web / adk api_server locally, Cloud Run in production).
const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
export const APP = import.meta.env.VITE_APP_NAME || 'campus_copilot'

function userId() {
  let id = null
  try { id = localStorage.getItem('cc-user') } catch { /* private mode */ }
  if (!id) {
    id = 'student-' + Math.random().toString(36).slice(2, 10)
    try { localStorage.setItem('cc-user', id) } catch { /* fine */ }
  }
  return id
}
export const USER = userId()

export async function createSession() {
  const r = await fetch(`${BASE}/apps/${APP}/users/${USER}/sessions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  })
  if (!r.ok) throw new Error(`Couldn't start a session (${r.status})`)
  return (await r.json()).id
}

export function fileToPart(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const [, b64] = String(reader.result).split(',')
      resolve({ inlineData: { mimeType: file.type || 'application/octet-stream', data: b64 } })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

/**
 * Sends one message and streams agent events.
 * onEvent receives {type: 'call', name} | {type: 'result', name, response} | {type: 'text', text}
 */
export async function sendMessage(sessionId, text, files, onEvent) {
  const parts = []
  for (const f of files) parts.push(await fileToPart(f))
  if (text.trim()) parts.push({ text: text.trim() })

  const r = await fetch(`${BASE}/run_sse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      appName: APP, userId: USER, sessionId,
      newMessage: { role: 'user', parts }, streaming: false,
    }),
  })
  if (!r.ok || !r.body) throw new Error(`The agent didn't respond (${r.status})`)

  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i)
      buf = buf.slice(i + 2)
      const data = chunk.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trim()).join('')
      if (!data) continue
      let ev
      try { ev = JSON.parse(data) } catch { continue }
      if (ev.error) throw new Error(ev.error)
      for (const p of ev.content?.parts || []) {
        if (p.functionCall) onEvent({ type: 'call', name: p.functionCall.name })
        else if (p.functionResponse) onEvent({ type: 'result', name: p.functionResponse.name, response: p.functionResponse.response || {} })
        else if (p.text && !p.thought) onEvent({ type: 'text', text: p.text })
      }
    }
  }
}
