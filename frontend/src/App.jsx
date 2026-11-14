import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createSession, sendMessage } from './api.js'
import { CARDS, TOOL_STATUS } from './cards.jsx'

const MAX_MB = 15
const ACCEPT = 'image/*,application/pdf'

const Mark = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18 L12 4 L20 18 L12 14 Z" fill="#FF4D1F" /></svg>
)
const Sun = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
)
const Moon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>
)
const Clip = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21.4 11.1 12.2 20.3a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5" /></svg>
)

async function sampleFile(path, name, type) {
  const r = await fetch(path)
  return new File([await r.blob()], name, { type })
}

const ACTIONS = [
  {
    n: '01', title: 'Plan my week', body: 'Study and chores fit around your classes, shifts and real energy.',
    try: 'Try it with a sample week',
    text: "Plan my week of Nov 16–22. Classes: CSE 30 MWF 10:40–11:45. Work: bookstore Tue/Thu 2–7pm and it's draining. Gym Mon/Wed 5–6pm. I'm a morning person. To do: essay draft due Friday, problem set due Thursday, laundry, groceries.",
  },
  {
    n: '02', title: 'Decode a letter', body: 'Financial aid, registrar, housing: what it means and what to do by when.',
    try: 'Try a sample FAFSA letter',
    text: 'What does this mean? Also explain it to my mom in Spanish.',
    file: ['/samples/sample_finaid_letter.png', 'finaid_letter.png', 'image/png'],
  },
  {
    n: '03', title: 'Import a syllabus', body: 'Every exam and deadline pulled out, then study time planned for you.',
    try: 'Try a sample CSE 30 syllabus',
    text: "Here's my CSE 30 syllabus.",
    file: ['/samples/sample_syllabus_cse30.pdf', 'cse30_syllabus.pdf', 'application/pdf'],
  },
  {
    n: '04', title: 'Find an office', body: 'Live Google Maps: open now, hours and how long the walk is.',
    try: 'Try: financial aid from Baskin',
    text: "Where's the Financial Aid Office? I'm at Baskin Engineering.",
  },
]

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'light')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem('cc-theme', theme) } catch { /* private mode */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

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

function AgentMessage({ msg, ask }) {
  return (
    <div className="msg-agent">
      <div className="avatar"><Mark /></div>
      <div className="agent-body">
        {msg.tools.map((t, i) => {
          const Card = CARDS[t.name]
          if (!Card) return null
          if (t.response?.status && t.response.status !== 'ok') return null
          return <Card key={i} r={t.response} ask={ask} />
        })}
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

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [drag, setDrag] = useState(false)
  const [note, setNote] = useState('')
  const session = useRef(null)
  const input = useRef(null)
  const picker = useRef(null)
  const bottom = useRef(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, busy])

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

  // Cmd/Ctrl+V a screenshot anywhere on the page.
  useEffect(() => {
    const onPaste = (e) => {
      const pasted = Array.from(e.clipboardData?.files || [])
      if (pasted.length) {
        e.preventDefault()
        addFiles(pasted.map((f, i) => (f.name && f.name !== 'image.png' ? f : new File([f], `screenshot-${Date.now()}-${i}.png`, { type: f.type }))))
        input.current?.focus()
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [addFiles])

  const send = useCallback(async (overrideText, overrideFiles) => {
    const t = overrideText ?? text
    const f = overrideFiles ?? files
    if (busy || (!t.trim() && f.length === 0)) return
    setText(''); setFiles([]); setNote('')
    setMessages((m) => [...m, { role: 'user', text: t, files: f }])
    setBusy(true); setStatus('Thinking')
    const reply = { role: 'agent', text: '', tools: [], error: '' }
    setMessages((m) => [...m, reply])
    const update = () => setMessages((m) => [...m.slice(0, -1), { ...reply, tools: [...reply.tools] }])
    try {
      if (!session.current) session.current = await createSession()
      await sendMessage(session.current, t, f, (ev) => {
        if (ev.type === 'call') setStatus(TOOL_STATUS[ev.name] || 'Working on it')
        if (ev.type === 'result') { reply.tools.push(ev); setStatus('Writing it up'); update() }
        if (ev.type === 'text') { reply.text += (reply.text ? '\n\n' : '') + ev.text; update() }
      })
      if (!reply.text && !reply.tools.length) reply.error = "I didn't get an answer back. Try again in a moment."
    } catch (err) {
      reply.error = /Failed to fetch|NetworkError|502|503|504/.test(String(err))
        ? "Can't reach the agent server. Make sure it's running (cd agent && adk web), then try again."
        : `Something went wrong: ${err.message}`
    } finally {
      update(); setBusy(false); setStatus('')
    }
  }, [busy, files, text])

  const ask = useCallback((t) => send(t, []), [send])

  const runAction = async (a) => {
    setText(a.text)
    if (a.file) {
      try { setFiles([await sampleFile(...a.file)]) } catch { setNote("Couldn't load the sample file.") }
    } else setFiles([])
    input.current?.focus()
  }

  const newChat = () => { session.current = null; setMessages([]); setText(''); setFiles([]); setNote('') }
  const empty = messages.length === 0

  return (
    <>
      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="#" onClick={(e) => { e.preventDefault(); newChat() }} aria-label="Campus Copilot home">
            <span className="brand-mark"><Mark /></span>
            <span className="brand-name">Campus Copilot</span>
            <span className="brand-sep" />
            <span className="label brand-sub">UC Santa Cruz</span>
          </a>
          <nav className="nav-links label" aria-label="Quick actions">
            {ACTIONS.map((a) => <button key={a.n} onClick={() => runAction(a)}>{a.title}</button>)}
          </nav>
          <div className="nav-actions">
            <button className="icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </button>
            <button className="pill primary" onClick={newChat}>New chat</button>
          </div>
        </div>
      </header>

      <main className="wrap">
        {empty ? (
          <section className="hero">
            <div className="label">Campus Copilot · an AI agent for college life</div>
            <h1 className="display" style={{ marginTop: 14 }}>
              Your week<span className="dot">.</span><br />Handled<span className="dot">.</span>
            </h1>
            <div className="hero-rule" />
            <div className="hero-row">
              <p className="hero-copy">
                <b>Campus Copilot</b> plans study and chores around your classes, shifts and energy,
                turns confusing official letters into next steps, and finds the office you need.
                Built for first-years figuring it out alone.
              </p>
              <div className="banner">
                <div>
                  <div className="label"><span className="live-dot" />Live · Gemini on Vertex AI</div>
                  <h3>Got a scary letter?</h3>
                  <p>Drop it here. You'll know what it means and what to do by when.</p>
                </div>
                <button className="pill primary" onClick={() => runAction(ACTIONS[1])}>Decode one →</button>
              </div>
            </div>

            <div className="actions">
              {ACTIONS.map((a) => (
                <button className="action" key={a.n} onClick={() => runAction(a)}>
                  <span className="num">{a.n}</span>
                  <h4>{a.title}</h4>
                  <p>{a.body}</p>
                  <span className="try">{a.try} →</span>
                </button>
              ))}
            </div>

            <div className="stats">
              <div className="stat"><span className="label">Tools</span><b>5 + voice</b></div>
              <div className="stat"><span className="label">Model</span><b>Gemini</b></div>
              <div className="stat"><span className="label">Places</span><b>Google Maps</b></div>
              <div className="stat"><span className="label">Built with</span><b>Google ADK</b></div>
            </div>
          </section>
        ) : (
          <section className="thread" aria-live="polite">
            {messages.map((m, i) => m.role === 'user' ? (
              <div className="msg-user" key={i}>
                {m.files.length > 0 && <div className="msg-files">{m.files.map((f, j) => <FilePreview key={j} file={f} />)}</div>}
                {m.text && <div className="bubble-user">{m.text}</div>}
              </div>
            ) : (
              <AgentMessage key={i} msg={m} ask={ask} />
            ))}
            {busy && (
              <div className="msg-agent">
                <div className="avatar"><Mark /></div>
                <div className="thinking"><span className="dots"><span /><span /><span /></span><span className="label">{status}…</span></div>
              </div>
            )}
            <div ref={bottom} />
          </section>
        )}
        {empty && <div style={{ height: 170 }} />}
      </main>

      <div
        className="composer-dock"
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(Array.from(e.dataTransfer.files || [])) }}
      >
        <div className={`composer ${drag ? 'drag' : ''}`}>
          {files.length > 0 && (
            <div className="composer-files">
              {files.map((f, i) => <FilePreview key={i} file={f} onRemove={() => setFiles((cur) => cur.filter((_, j) => j !== i))} />)}
            </div>
          )}
          <div className="composer-row">
            <button className="icon-btn" onClick={() => picker.current?.click()} aria-label="Attach a photo or PDF"><Clip /></button>
            <input ref={picker} type="file" accept={ACCEPT} multiple hidden onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
            <textarea
              ref={input}
              rows={1}
              value={text}
              placeholder="Ask anything, or paste a screenshot (⌘V) of a letter, schedule or syllabus…"
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              aria-label="Message Campus Copilot"
            />
            <button className="pill primary" onClick={() => send()} disabled={busy || (!text.trim() && !files.length)}>
              {busy ? 'Working' : 'Send →'}
            </button>
          </div>
        </div>
        <div className="hint">{note || 'Enter to send · Shift+Enter for a new line · Drop or paste images and PDFs'}</div>
      </div>
    </>
  )
}
