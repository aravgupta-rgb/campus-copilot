import { useEffect, useState } from 'react'
import { Composer, Mark, Thread, useChat } from './Chat.jsx'

const QUICK = ['How do I drop a class?', "What's a good study routine for midterms?", 'How do I talk to a professor about an extension?']

/** Floating "Ask Copilot" button + slide-over chat for quick questions, on every page. */
export default function SideAssistant({ hidden }) {
  const [open, setOpen] = useState(false)
  const chat = useChat()

  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (hidden) return null
  return (
    <>
      {!open && (
        <button className="assist-fab" onClick={() => setOpen(true)} aria-label="Ask Copilot a quick question">
          <span className="avatar"><Mark /></span><span>Ask Copilot</span>
        </button>
      )}
      <aside className={`assist ${open ? 'open' : ''}`} aria-hidden={!open} aria-label="Quick questions">
        <div className="assist-head">
          <div>
            <div className="label accent">Quick questions</div>
            <b>Ask Copilot anything</b>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {chat.messages.length > 0 && <button className="pill ghost small" onClick={chat.reset}>Clear</button>}
            <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>
        </div>
        <div className="assist-body">
          {chat.messages.length === 0 ? (
            <div className="assist-empty">
              <p>Random college question? Ask here without leaving the page.</p>
              {QUICK.map((q) => <button key={q} className="chip-btn" onClick={() => chat.send(q)}>{q}</button>)}
            </div>
          ) : (
            <Thread chat={chat} compact />
          )}
        </div>
        <div className="assist-foot">
          <Composer chat={chat} size="compact" pasteTarget="box" placeholder="Ask a quick question…" />
        </div>
      </aside>
    </>
  )
}
