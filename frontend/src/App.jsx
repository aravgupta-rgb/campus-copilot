import { useCallback, useEffect, useState } from 'react'
import { Composer, Mark, MicIcon, Thread, useChat } from './Chat.jsx'
import SideAssistant from './SideAssistant.jsx'
import VoiceMode from './VoiceMode.jsx'

const SKIN = import.meta.env.VITE_SKIN || 'bold'

const Sun = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
)
const Moon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>
)

async function sampleFile(path, name, type) {
  const r = await fetch(path)
  return new File([await r.blob()], name, { type })
}

const FEATURES = [
  {
    n: '01', key: 'plan', title: 'Plans your week', tag: 'Life Blocker',
    body: 'Tell it your classes, shifts and gym, or screenshot your work schedule. It fits study and chores where your energy actually is, checks every block for conflicts, and books it when you say so.',
    text: "Plan my week of Nov 16–22. Classes: CSE 30 MWF 10:40–11:45. Work: bookstore Tue/Thu 2–7pm and it's draining. Gym Mon/Wed 5–6pm. I'm a morning person. To do: essay draft due Friday, problem set due Thursday, laundry, groceries.",
  },
  {
    n: '02', key: 'decode', title: 'Decodes scary letters', tag: 'Decode',
    body: 'Financial aid, registrar, housing. Snap a photo and get what it means, how urgent it is, every step with its deadline, who to contact, a ready email, and a version for your family in their language.',
    text: 'What does this mean? Also explain it to my mom in Spanish.',
    file: ['/samples/sample_finaid_letter.png', 'finaid_letter.png', 'image/png'],
  },
  {
    n: '03', key: 'syllabus', title: 'Reads your syllabus', tag: 'Syllabus Import',
    body: 'Drop in a syllabus PDF. Every exam, assignment and class time comes out, exams become study sessions, and it plans them into your week before the cramming starts.',
    text: "Here's my CSE 30 syllabus.",
    file: ['/samples/sample_syllabus_cse30.pdf', 'cse30_syllabus.pdf', 'application/pdf'],
  },
  {
    n: '04', key: 'office', title: 'Finds the right office', tag: 'Office Finder',
    body: 'Live Google Maps data: whether it is open right now, its hours, phone number and how long the walk is from where you are standing.',
    text: "Where's the Financial Aid Office? I'm at Baskin Engineering.",
  },
]

const SUGGESTIONS = [
  { label: 'Plan my week', f: 0 },
  { label: 'Decode a sample letter', f: 1 },
  { label: 'Read a sample syllabus', f: 2 },
  { label: "Where's financial aid?", f: 3 },
]

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'light')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem('cc-theme', theme) } catch { /* private mode */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const chat = useChat()
  const [prefill, setPrefill] = useState(null)
  const [voice, setVoice] = useState(false)
  const chatting = chat.messages.length > 0

  useEffect(() => { document.documentElement.setAttribute('data-skin', SKIN) }, [])

  const tryFeature = useCallback(async (f) => {
    let files = []
    if (f.file) { try { files = [await sampleFile(...f.file)] } catch { /* sample missing: text only */ } }
    setPrefill({ text: f.text, files })
    if (!chatting) window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [chatting])

  const home = () => { chat.reset(); setPrefill(null); window.scrollTo({ top: 0 }) }
  const jump = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <>
      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="#" onClick={(e) => { e.preventDefault(); home() }} aria-label="Campus Copilot home">
            <span className="brand-mark"><Mark /></span>
            <span className="brand-name">Campus Copilot</span>
          </a>
          {!chatting && (
            <nav className="nav-links" aria-label="Sections">
              <button onClick={() => jump('features')}>Features</button>
              <button onClick={() => jump('how')}>How it works</button>
              <button onClick={() => jump('voice')}>Voice</button>
            </nav>
          )}
          <div className="nav-actions">
            <button className="icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </button>
            {chatting
              ? <button className="pill ghost" onClick={home}>New chat</button>
              : <button className="pill primary" onClick={() => setVoice(true)}><MicIcon /> Talk to it</button>}
          </div>
        </div>
      </header>

      {!chatting ? (
        <main>
          <section className="hero-agent wrap">
            <div className="glow" aria-hidden="true" />
            <div className="eyebrow label"><span className="live-dot" /> AI agent for college life · powered by Gemini</div>
            <h1 className="display hero-title">
              <span className="h-a">Meet your</span>
              <span className="h-b">campus copilot<span className="dot">.</span></span>
            </h1>
            <p className="hero-sub">
              One AI agent that plans your week around your real energy, explains confusing college letters,
              reads your syllabus and finds any office on campus. Type, paste a screenshot, or just talk.
            </p>
            <div className="hero-composer">
              <Composer chat={chat} prefill={prefill} onVoice={() => setVoice(true)} size="hero" placeholder="Ask Campus Copilot anything, or paste a screenshot (⌘V)…" />
              <div className="suggestions">
                {SUGGESTIONS.map((s) => <button key={s.label} className="chip-btn" onClick={() => tryFeature(FEATURES[s.f])}>{s.label}</button>)}
              </div>
            </div>
            <div className="built-on label">
              <span>Built on</span><b>Gemini</b><b>Vertex AI</b><b>Google Maps</b><b>Google ADK</b><b>Cloud Run</b>
            </div>
          </section>

          <section id="features" className="section wrap">
            <div className="section-head">
              <div className="label accent">What it does</div>
              <h2 className="display">Four jobs<span className="dot">.</span> One agent<span className="dot">.</span></h2>
              <p>You don't pick a tool. Ask in your own words and Campus Copilot decides which ones to use, often several in a row.</p>
            </div>
            <div className="features">
              {FEATURES.map((f) => (
                <article className={`feature f-${f.key}`} key={f.key}>
                  <div className="feature-top"><span className="num">{f.n}</span><span className="chip">{f.tag}</span></div>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                  <button className="pill ghost" onClick={() => tryFeature(f)}>Try it <span aria-hidden="true">→</span></button>
                </article>
              ))}
            </div>
          </section>

          <section id="how" className="section wrap">
            <div className="section-head">
              <div className="label accent">How it works</div>
              <h2 className="display">Gemini proposes<span className="dot">.</span> Code verifies<span className="dot">.</span></h2>
            </div>
            <ol className="how">
              <li><span className="num">1</span><h4>You ask</h4><p>Type it, paste a screenshot of a letter or schedule, drop a syllabus PDF, or talk out loud.</p></li>
              <li><span className="num">2</span><h4>The agent picks tools</h4><p>A Google ADK agent on Gemini decides what to run: the planner, the letter decoder, the syllabus reader or Google Maps.</p></li>
              <li><span className="num">3</span><h4>Code double-checks</h4><p>Every plan is checked for overlaps, energy rules and due dates. Nothing touches your calendar until you approve it.</p></li>
            </ol>
          </section>

          <section id="voice" className="section wrap">
            <div className="banner voice-banner">
              <div>
                <div className="label"><span className="live-dot" />Voice · Gemini Live</div>
                <h3>Rather just talk?</h3>
                <p>Ask out loud while you walk to class. Campus Copilot answers back and still plans, decodes and finds offices for you.</p>
              </div>
              <button className="pill primary" onClick={() => setVoice(true)}><MicIcon /> Start talking</button>
            </div>
          </section>

          <footer className="footer wrap">
            <div className="brand"><span className="brand-mark"><Mark /></span><span className="brand-name">Campus Copilot</span></div>
            <p>Built at Google DevFest UCSC 2026 by Gupta Tech Bros. Always confirm deadlines with the office named in your letter.</p>
          </footer>
          <div style={{ height: 40 }} />
        </main>
      ) : (
        <main className="wrap chat-view">
          <Thread chat={chat} />
          <div className="composer-dock">
            <Composer chat={chat} prefill={prefill} onVoice={() => setVoice(true)} placeholder="Reply, ask something new, or paste a screenshot…" autoFocus />
            <div className="hint">Enter to send · Shift+Enter for a new line · Drop or paste images and PDFs</div>
          </div>
        </main>
      )}

      <SideAssistant hidden={voice} />
      <VoiceMode open={voice} onClose={() => setVoice(false)} />
    </>
  )
}
