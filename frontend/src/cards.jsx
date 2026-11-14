// Rich cards for each agent tool result. Each card gets the tool's JSON response
// (see CONTRACTS.md) and an `ask` function to send a follow-up message.

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
const DOW = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

function ymd(s) {
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}
export function shortDate(s) {
  if (!s) return ''
  const d = ymd(s)
  return `${DOW[d.getUTCDay()]} ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`
}
function clock(iso) {
  const [h, m] = String(iso).slice(11, 16).split(':').map(Number)
  const ap = h >= 12 ? 'PM' : 'AM'
  const hh = h % 12 || 12
  return m ? `${hh}:${String(m).padStart(2, '0')} ${ap}` : `${hh} ${ap}`
}
function minutes(a, b) { return (new Date(b) - new Date(a)) / 60000 }

/* ---------------- Life Blocker ---------------- */
export function PlanCard({ r, ask }) {
  const blocks = r.proposed_blocks || []
  if (!blocks.length) return null
  const dates = blocks.map((b) => b.start.slice(0, 10)).sort()
  const first = ymd(dates[0])
  const last = ymd(dates[dates.length - 1])
  const span = Math.max(6, Math.round((last - first) / 864e5))
  const days = Array.from({ length: span + 1 }, (_, i) => new Date(first.getTime() + i * 864e5))
  const hrs = blocks.reduce((s, b) => s + minutes(b.start, b.end), 0) / 60
  const left = r.unscheduled || []

  return (
    <div className="card">
      <div className="plan-head">
        <div>
          <div className="label accent">Life Blocker · preview, not booked yet</div>
          <h3>Your week, planned<span className="dot">.</span></h3>
        </div>
        <div className="plan-stats">
          <span>{blocks.length} blocks</span>
          <span>{hrs % 1 ? hrs.toFixed(1) : hrs} hrs</span>
          <span>{left.length ? `${left.length} didn't fit` : '0 conflicts'}</span>
        </div>
      </div>

      <div className="week" role="list">
        {days.map((d) => {
          const key = d.toISOString().slice(0, 10)
          const mine = blocks.filter((b) => b.start.slice(0, 10) === key)
          return (
            <div className={`day ${mine.length ? 'has' : ''}`} key={key} role="listitem">
              <div className="day-top"><span className="dow">{DOW[d.getUTCDay()]}</span><span className="dnum">{d.getUTCDate()}</span></div>
              {mine.length === 0 && <div className="empty-day">Free</div>}
              {mine.map((b, i) => {
                const energy = (b.description?.match(/\((high|medium|low) energy\)/) || [])[1] || 'low'
                return (
                  <div className={`block ${energy}`} key={i} title={b.description}>
                    <div className="t">{clock(b.start)}–{clock(b.end)}</div>
                    <div className="title">{b.title}</div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>

      <div className="card-row">
        <span className="chip high">High focus</span>
        <span className="chip medium">Medium</span>
        <span className="chip low">Low energy</span>
      </div>

      {left.length > 0 && (
        <p className="warn">Didn't fit: {left.map((u) => `${u.task} (${u.minutes_left} min)`).join(', ')}</p>
      )}

      <div className="offer">
        <div>
          <div className="label accent">Looks good?</div>
          <b>{blocks.length} blocks · {hrs % 1 ? hrs.toFixed(1) : hrs} hrs</b>
        </div>
        <button className="pill primary" onClick={() => ask('Book these on my Google Calendar.')}>Book it on Google Calendar →</button>
      </div>
    </div>
  )
}

/* ---------------- Decode ---------------- */
export function DecodeCard({ r, ask }) {
  if (r.status !== 'ok') return null
  const u = r.urgency || 'medium'
  const steps = r.action_items || []
  return (
    <div className="card decode">
      <div className="card-head">
        <span className={`urgency ${u}`}><i />{u} urgency</span>
        <span className="label">Decoded letter</span>
      </div>
      <p className="summary">{r.summary}</p>
      <p className="means">{r.what_it_means}</p>

      {steps.length > 0 && (
        <ol className="steps">
          {steps.map((s, i) => (
            <li key={i}>
              <span className="n">{String(i + 1).padStart(2, '0')}</span>
              <span>{s.task}</span>
              <span className="due">{s.due ? `Due ${shortDate(s.due)}` : ''}</span>
            </li>
          ))}
        </ol>
      )}

      {r.contact && (
        <p className="kv" style={{ color: 'inherit', opacity: 0.85 }}>
          Contact: <b>{r.contact.name}</b>
          {r.contact.email && <> · <a href={`mailto:${r.contact.email}`} style={{ color: 'inherit' }}>{r.contact.email}</a></>}
          {r.contact.phone && <> · {r.contact.phone}</>}
        </p>
      )}

      {r.draft_reply && (
        <details className="more">
          <summary>Email I drafted for you</summary>
          <pre>{r.draft_reply}</pre>
          <button className="pill on-dark" style={{ marginTop: 10 }} onClick={() => navigator.clipboard?.writeText(r.draft_reply)}>Copy email</button>
        </details>
      )}
      {r.translation && (
        <details className="more">
          <summary>For family · {r.translation.language}</summary>
          <pre>{r.translation.text}</pre>
        </details>
      )}

      <div className="card-row">
        {steps.length > 0 && <button className="pill primary" onClick={() => ask('Yes, block time in my week for these steps.')}>Block time for this →</button>}
        {r.contact?.name && <button className="pill on-dark" onClick={() => ask(`Where is the ${r.contact.name}? Is it open?`)}>Find the office</button>}
      </div>
      {r.verify_note && <p className="label" style={{ marginTop: 14, textTransform: 'none', letterSpacing: 0 }}>{r.verify_note}</p>}
    </div>
  )
}

/* ---------------- Office Finder ---------------- */
export function OfficeCard({ r }) {
  if (r.status !== 'ok') return null
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long' })
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <div className="label accent">Office Finder · Google Maps</div>
          <h3>{r.name}</h3>
        </div>
        {r.open_now !== null && r.open_now !== undefined && (
          <span className={`chip ${r.open_now ? 'open' : 'closed'}`}>{r.open_now ? 'Open now' : 'Closed now'}</span>
        )}
      </div>
      <div className="office-grid">
        <div>
          {r.walk ? (
            <>
              <div className="walk">{r.walk.minutes} min walk</div>
              <p className="kv">{r.walk.miles} mi from {r.walk.from}</p>
            </>
          ) : (
            <div className="label">Tell me where you are for walking time</div>
          )}
          <p className="kv">{r.address}</p>
          {r.phone && <p className="kv"><a href={`tel:${r.phone.replace(/[^\d+]/g, '')}`}>{r.phone}</a></p>}
          <div className="card-row">
            {r.walk?.directions_link && <a className="pill primary" href={r.walk.directions_link} target="_blank" rel="noreferrer">Directions →</a>}
            {r.maps_link && <a className="pill ghost" href={r.maps_link} target="_blank" rel="noreferrer">Open in Maps</a>}
            {r.website && <a className="pill ghost" href={r.website} target="_blank" rel="noreferrer">Website</a>}
          </div>
        </div>
        {r.hours?.length > 0 && (
          <ul className="hours" aria-label="Opening hours">
            {r.hours.map((h) => {
              const [day, ...rest] = h.split(': ')
              return <li key={day} className={day === today ? 'today' : ''}><span>{day}</span><span>{rest.join(': ')}</span></li>
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

/* ---------------- Syllabus Import ---------------- */
export function SyllabusCard({ r, ask }) {
  if (r.status !== 'ok') return null
  const items = [...(r.deadlines || [])].sort((a, b) => a.start.localeCompare(b.start))
  return (
    <div className="card">
      <div className="label accent">Syllabus Import</div>
      <h3>{r.course}</h3>
      {r.grading_summary && <p className="kv">{r.grading_summary}</p>}
      {r.class_meetings?.length > 0 && (
        <div className="card-row">
          {r.class_meetings.map((m, i) => <span className="chip" key={i}>{m.title} · {m.days.join('/')} {m.start}–{m.end}</span>)}
        </div>
      )}
      <ul className="deadlines">
        {items.map((e, i) => {
          const exam = /midterm|final|exam|quiz/i.test(e.title)
          return (
            <li key={i}>
              <span className="d">{shortDate(e.start)}</span>
              <span className={exam ? 'exam' : ''}>{exam ? '📝 ' : ''}{e.title.replace(/^[^:]+:\s*/, '')}</span>
            </li>
          )
        })}
      </ul>
      {r.undated?.length > 0 && <p className="warn">No date given: {r.undated.join(', ')}</p>}
      <div className="card-row">
        <button className="pill primary" onClick={() => ask('Plan study time for these over the next week.')}>Plan study time →</button>
      </div>
    </div>
  )
}

/* ---------------- Schedule screenshot ---------------- */
export function ScheduleReadCard({ r }) {
  if (r.status !== 'ok') return null
  return (
    <div className="card">
      <div className="label accent">Read from your screenshot</div>
      <ul className="deadlines">
        {(r.fixed || []).map((f, i) => (
          <li key={i}>
            <span className="d">{f.days?.length ? f.days.join('/') : shortDate(f.start)}</span>
            <span>{f.title} · {f.start.includes('T') ? `${clock(f.start)}–${clock(f.end)}` : `${f.start}–${f.end}`}</span>
          </li>
        ))}
      </ul>
      {r.check_these?.length > 0 && <p className="warn">Double-check: {r.check_these.join(', ')}</p>}
    </div>
  )
}

export const CARDS = {
  plan_life_blocks: PlanCard,
  decode_document: DecodeCard,
  find_office: OfficeCard,
  import_syllabus: SyllabusCard,
  read_schedule_screenshot: ScheduleReadCard,
}

export const TOOL_STATUS = {
  plan_life_blocks: 'Planning your week around your energy',
  decode_document: 'Decoding your letter',
  find_office: 'Checking Google Maps',
  import_syllabus: 'Reading your syllabus',
  read_schedule_screenshot: 'Reading your schedule',
}
