import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createSession, sendMessage } from './api.js'
import { CARDS, TOOL_STATUS } from './cards.jsx'

const MAX_MB = 15
export const ACCEPT = 'image/*,application/pdf'

export const Mark = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18 L12 4 L20 18 L12 14 Z" fill="#FF4D1F" /></svg>
)
export const Clip = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21.4 11.1 12.2 20.3a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5" /></svg>
)
export const MicIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4" /></svg>
)

function FilePreview({ file, onRemove }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!file.type.startsWith('image/')) return
    const u = URL.createObjectURL(file)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [file])
  return (
    <div className="pending-file">
      {url ? <img src={url} alt="" /> : <span className="ext">{(file.name.split('.').pop() || 'FILE').slice(0, 3).toUpperCase()}</span>}
      <span>{file.name}</span>
      {onRemove && <button onClick={onRemove} aria-label={`Remove ${file.name}`}>×</button>}
    </div>
  )
}

export function ToolCards({ tools, ask }) {
  return tools.map((t, i) => {
    const Card = CARDS[t.name]
    if (!Card || (t.response?.status && t.response.status !== 'ok')) return null
    return <Card key={i} r={t.response} ask={ask} />
  })
}

function AgentMessage({ msg, ask, compact }) {
  return (
    <div className="msg-agent">
      <div className="avatar"><Mark /></div>
      <div className="agent-body">
        {!compact && <ToolCards tools={msg.tools} ask={ask} />}
        {compact && msg.tools.length > 0 && (
          <div className="label">{msg.tools.map((t) => TOOL_STATUS[t.name] || t.name).join(' · ')}</div>
        )}
        {msg.text && (
          <div className="agent-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer" /> }}>
              {msg.text}
            </ReactMarkdown>
          </div>
        )}
        {msg.error && <div className="error-note">{msg.error}</div>}
      </div>
    </div>
  )
}

/** All chat state for one conversation (main page and side assistant each get one). */
export function useChat() {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const session = useRef(null)

  const send = useCallback(async (text, files = []) => {
    if (busy || (!text.trim() && files.length === 0)) return false
    setMessages((m) => [...m, { role: 'user', text, files }])
    setBusy(true); setStatus('Thinking')
    const reply = { role: 'agent', text: '', tools: [], error: '' }
    setMessages((m) => [...m, reply])
    const update = () => setMessages((m) => [...m.slice(0, -1), { ...reply, tools: [...reply.tools] }])
    try {
      if (!session.current) session.current = await createSession()
      await sendMessage(session.current, text, files, (ev) => {
        if (ev.type === 'call') setStatus(TOOL_STATUS[ev.name] || 'Working on it')
        if (ev.type === 'result') { reply.tools.push(ev); setStatus('Writing it up'); update() }
        if (ev.type === 'text') { reply.text += (reply.text ? '\n\n' : '') + ev.text; update() }
      })
      if (!reply.text && !reply.tools.length) reply.error = "I didn't get an answer back. Try again in a moment."
    } catch (err) {
      reply.error = /Failed to fetch|NetworkError|502|503|504/.test(String(err))
        ? "Can't reach Campus Copilot right now. Check the agent server is running, then try again."
        : `Something went wrong: ${err.message}`
    } finally {
      update(); setBusy(false); setStatus('')
    }
    return true
  }, [busy])

  const reset = useCallback(() => { session.current = null; setMessages([]) }, [])
  return { messages, busy, status, send, reset }
}

export function Thread({ chat, compact = false }) {
  const bottom = useRef(null)
  const ask = useCallback((t) => chat.send(t, []), [chat])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [chat.messages, chat.busy])
  return (
    <div className={`thread ${compact ? 'compact' : ''}`} aria-live="polite">
      {chat.messages.map((m, i) => m.role === 'user' ? (
        <div className="msg-user" key={i}>
          {m.files.length > 0 && <div className="msg-files">{m.files.map((f, j) => <FilePreview key={j} file={f} />)}</div>}
          {m.text && <div className="bubble-user">{m.text}</div>}
        </div>
      ) : (
        <AgentMessage key={i} msg={m} ask={ask} compact={compact} />
      ))}
      {chat.busy && (
        <div className="msg-agent">
          <div className="avatar"><Mark /></div>
          <div className="thinking"><span className="dots"><span /><span /><span /></span><span className="label">{chat.status}…</span></div>
        </div>
      )}
      <div ref={bottom} />
    </div>
  )
}

/** Message box with attach, drag-drop and ⌘V paste. `prefill` lets parents load text/files into it. */
export function Composer({ chat, prefill, onSent, onVoice, placeholder, pasteTarget = 'window', size = 'dock', autoFocus = false }) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [drag, setDrag] = useState(false)
  const [note, setNote] = useState('')
  const input = useRef(null)
  const picker = useRef(null)
  const box = useRef(null)

  useEffect(() => {
    // A suggestion fills a box once. After it's sent, the chat view's box must not
    // pick the same question up again.
    if (!prefill || prefill.used) return
    prefill.used = true
    setText(prefill.text || '')
    setFiles(prefill.files || [])
    // Templates: highlight the first [blank] so the student can just start typing.
    requestAnimationFrame(() => {
      const el = input.current
      if (!el) return
      el.focus()
      const t = prefill.text || ''
      const s = prefill.selectBlank ? t.indexOf('[') : -1
      const e = s >= 0 ? t.indexOf(']', s) : -1
      if (s >= 0 && e > s) el.setSelectionRange(s, e + 1)
      else el.setSelectionRange(t.length, t.length)
    })
  }, [prefill])

  // Tab jumps to the next [blank] in a template.
  const nextBlank = (e) => {
    if (e.key !== 'Tab' || e.shiftKey) return false
    const el = input.current
    const s = text.indexOf('[', el.selectionEnd)
    const s2 = s >= 0 ? s : text.indexOf('[')
    if (s2 < 0) return false
    const end = text.indexOf(']', s2)
    if (end < 0) return false
    e.preventDefault()
    el.setSelectionRange(s2, end + 1)
    return true
  }

  useEffect(() => {
    const el = input.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }, [text])

  const addFiles = useCallback((list) => {
    const ok = []
    for (const f of list) {
      if (!(f.type.startsWith('image/') || f.type === 'application/pdf')) { setNote(`${f.name}: only images and PDFs work here.`); continue }
      if (f.size > MAX_MB * 1024 * 1024) { setNote(`${f.name} is over ${MAX_MB} MB.`); continue }
      ok.push(f)
    }
    if (ok.length) { setFiles((cur) => [...cur, ...ok].slice(0, 4)); setNote('') }
  }, [])

  useEffect(() => {
    const target = pasteTarget === 'window' ? window : box.current
    if (!target) return
    const onPaste = (e) => {
      const pasted = Array.from(e.clipboardData?.files || [])
      if (!pasted.length) return
      e.preventDefault()
      addFiles(pasted.map((f, i) => (f.name && f.name !== 'image.png' ? f : new File([f], `screenshot-${Date.now()}-${i}.png`, { type: f.type }))))
      input.current?.focus()
    }
    target.addEventListener('paste', onPaste)
    return () => target.removeEventListener('paste', onPaste)
  }, [addFiles, pasteTarget])

  const submit = async () => {
    // Template clean-up: drop an unfilled optional line, strip the "Optional:" label.
    let t = text
      .split('\n')
      .filter((line) => !(/^\s*Optional:/i.test(line) && /\[[^\]]*\]/.test(line)))
      .map((line) => line.replace(/^\s*Optional:\s*/i, ''))
      .join('\n')
    const f = files
    if (chat.busy || (!t.trim() && !f.length)) return
    const blank = t.match(/\[(Month Day–Day|class abbreviation|days|start–end time|job|assignment or task|day)\]/)
    if (blank) {
      setNote(`Fill in ${blank[0]} first. Tab jumps to the next blank.`)
      const s = t.indexOf(blank[0])
      input.current?.setSelectionRange(text.indexOf(blank[0]), text.indexOf(blank[0]) + blank[0].length)
      input.current?.focus()
      return s
    }
    setText(''); setFiles([]); setNote('')
    onSent?.() // parent drops the loaded suggestion so no box re-fills with it
    await chat.send(t, f)
  }

  return (
    <div
      ref={box}
      className={`composer composer-${size} ${drag ? 'drag' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(Array.from(e.dataTransfer.files || [])) }}
    >
      {files.length > 0 && (
        <div className="composer-files">
          {files.map((f, i) => <FilePreview key={i} file={f} onRemove={() => setFiles((cur) => cur.filter((_, j) => j !== i))} />)}
        </div>
      )}
      <div className="composer-row">
        <button className="icon-btn" onClick={() => picker.current?.click()} aria-label="Attach a photo or PDF" title="Attach a photo or PDF"><Clip /></button>
        <input ref={picker} type="file" accept={ACCEPT} multiple hidden onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
        <textarea
          ref={input}
          rows={1}
          value={text}
          autoFocus={autoFocus}
          placeholder={placeholder || 'Ask Campus Copilot anything…'}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (nextBlank(e)) return
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
          }}
          aria-label="Message Campus Copilot"
        />
        {onVoice && <button className="icon-btn voice-btn" onClick={onVoice} aria-label="Talk to Campus Copilot" title="Talk"><MicIcon /></button>}
        <button className="pill primary" onClick={submit} disabled={chat.busy || (!text.trim() && !files.length)}>
          {chat.busy ? 'Working' : 'Send'} <span aria-hidden="true">→</span>
        </button>
      </div>
      {note && <div className="composer-note">{note}</div>}
    </div>
  )
}
