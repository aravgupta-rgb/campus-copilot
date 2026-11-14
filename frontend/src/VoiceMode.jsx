import { useEffect, useRef, useState } from 'react'
import { ToolCards } from './Chat.jsx'
import { startVoice } from './voice.js'

const LABEL = {
  connecting: 'Connecting',
  listening: 'Listening',
  speaking: 'Copilot is talking',
  closed: 'Call ended',
}

export default function VoiceMode({ open, onClose }) {
  const [state, setState] = useState('connecting')
  const [lines, setLines] = useState([])
  const [tools, setTools] = useState([])
  const stopRef = useRef(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLines([]); setTools([]); setState('connecting')
    startVoice({
      onState: (s) => !cancelled && setState(s),
      onTranscript: (who, text, partial) => {
        if (cancelled) return
        setLines((ls) => {
          const last = ls[ls.length - 1]
          if (last && last.who === who && last.partial) return [...ls.slice(0, -1), { who, text: partial ? last.text + text : text, partial }]
          return [...ls, { who, text, partial }].slice(-8)
        })
      },
      onTool: (t) => !cancelled && setTools((ts) => [...ts, t]),
    })
      .then((stop) => { if (cancelled) stop(); else stopRef.current = stop })
      .catch((err) => !cancelled && setState(`error:${/Permission|NotAllowed/.test(String(err)) ? 'Microphone access was blocked. Allow it in your browser and try again.' : err.message}`))
    return () => { cancelled = true; stopRef.current?.(); stopRef.current = null }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  const err = state.startsWith('error:') ? state.slice(6) : ''
  return (
    <div className="voice-overlay" role="dialog" aria-modal="true" aria-label="Talk to Campus Copilot">
      <div className="voice-panel">
        <div className="label accent">Voice · Gemini Live</div>
        <div className={`orb ${err ? 'error' : state}`} aria-hidden="true"><span /><span /><span /></div>
        <div className="voice-state">{err ? 'Something went wrong' : LABEL[state] || state}</div>
        {err ? <p className="voice-hint">{err}</p> : (
          <p className="voice-hint">Try: “Plan my week. I work Tuesday and Thursday afternoons and I'm a morning person.”</p>
        )}
        {lines.length > 0 && (
          <div className="voice-lines">
            {lines.map((l, i) => <p key={i} className={l.who}><b>{l.who === 'you' ? 'You' : 'Copilot'}</b> {l.text}</p>)}
          </div>
        )}
        {tools.length > 0 && <div className="voice-cards"><ToolCards tools={tools} ask={() => {}} /></div>}
        <button className="pill primary end-call" onClick={onClose}>End conversation</button>
      </div>
    </div>
  )
}
