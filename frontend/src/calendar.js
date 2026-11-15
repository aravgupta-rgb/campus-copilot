// Booking Life Blocker plans into the student's calendar.
// 1) Google Calendar API, with the student's own Google sign-in (Google Identity Services).
//    The access token stays in this browser tab; the agent never sees it.
// 2) Fallbacks that need no setup: a .ics file and per-event Google Calendar links.

// OAuth Web client ID (public by design; the client *secret* is never used or stored here).
// Authorized JS origins: the Cloud Run URL and localhost:5173/5175.
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
  || '261781875474-fcg86jt9v0q4607g1sadb6ndlrjqlnrf.apps.googleusercontent.com'
const SCOPE = 'https://www.googleapis.com/auth/calendar.events'
const TZ = 'America/Los_Angeles'
// Google Calendar event colors: 9 = blueberry (focus), 5 = banana (medium), 2 = sage (low)
const COLOR = { high: '9', medium: '5', low: '2' }

export const canUseGoogle = () => Boolean(CLIENT_ID)

function energyOf(b) {
  return (b.description?.match(/\((high|medium|low) energy\)/) || [])[1] || 'low'
}

let gisLoading = null
function loadGis() {
  if (window.google?.accounts?.oauth2) return Promise.resolve()
  if (!gisLoading) {
    gisLoading = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = 'https://accounts.google.com/gsi/client'
      s.async = true
      s.onload = () => resolve()
      s.onerror = () => { gisLoading = null; reject(new Error("Couldn't load Google sign-in.")) }
      document.head.appendChild(s)
    })
  }
  return gisLoading
}

let cached = null // { token, expires }
async function getToken() {
  if (cached && cached.expires > Date.now() + 60_000) return cached.token
  await loadGis()
  return new Promise((resolve, reject) => {
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID,
      scope: SCOPE,
      callback: (resp) => {
        if (resp.error) return reject(new Error(resp.error_description || resp.error))
        cached = { token: resp.access_token, expires: Date.now() + (resp.expires_in || 3000) * 1000 }
        window.dispatchEvent(new Event('cc-calendar'))
        resolve(resp.access_token)
      },
      error_callback: (err) => reject(new Error(err?.type === 'popup_closed' ? 'Sign-in was closed before finishing.' : (err?.message || 'Google sign-in failed.'))),
    })
    client.requestAccessToken({ prompt: cached ? '' : 'consent' })
  })
}

/** Signs in with Google (popup) so the agent can read and book the calendar. */
export async function connectGoogle() {
  await getToken()
  window.dispatchEvent(new Event('cc-calendar'))
}

/** The current token if the student is connected (no popup), else null. */
export function cachedToken() {
  return cached && cached.expires > Date.now() + 60_000 ? cached.token : null
}

/** Creates every block in the student's primary Google Calendar. Returns { created, links }. */
export async function bookOnGoogle(blocks) {
  const token = await getToken()
  const links = []
  for (const b of blocks) {
    const energy = energyOf(b)
    const r = await fetch('https://www.googleapis.com/calendar/v3/calendars/primary/events', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        summary: b.title,
        description: `${b.description || ''}\n\nPlanned by Campus Copilot.`,
        start: { dateTime: b.start, timeZone: TZ },
        end: { dateTime: b.end, timeZone: TZ },
        colorId: COLOR[energy],
        reminders: { useDefault: false, overrides: [{ method: 'popup', minutes: 10 }] },
        source: { title: 'Campus Copilot', url: window.location.origin },
      }),
    })
    if (r.status === 401) { cached = null; throw new Error('Google sign-in expired. Tap Book it again.') }
    if (!r.ok) {
      const msg = (await r.json().catch(() => ({})))?.error?.message || `Calendar error ${r.status}`
      throw new Error(msg)
    }
    links.push((await r.json()).htmlLink)
  }
  return { created: links.length, links }
}

/* ---------------- no-setup fallbacks ---------------- */
const icsStamp = (iso) => new Date(iso).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
const esc = (s) => String(s || '').replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/[,;]/g, (m) => `\\${m}`)

/** Downloads one .ics file with every block (opens in Google, Apple or Outlook Calendar). */
export function downloadIcs(blocks, name = 'campus-copilot-week.ics') {
  const now = icsStamp(new Date().toISOString())
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Campus Copilot//Life Blocker//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']
  blocks.forEach((b, i) => {
    lines.push('BEGIN:VEVENT', `UID:cc-${Date.now()}-${i}@campus-copilot`, `DTSTAMP:${now}`,
      `DTSTART:${icsStamp(b.start)}`, `DTEND:${icsStamp(b.end)}`, `SUMMARY:${esc(b.title)}`,
      `DESCRIPTION:${esc((b.description || '') + ' · Planned by Campus Copilot')}`,
      'BEGIN:VALARM', 'TRIGGER:-PT10M', 'ACTION:DISPLAY', `DESCRIPTION:${esc(b.title)}`, 'END:VALARM', 'END:VEVENT')
  })
  lines.push('END:VCALENDAR')
  const url = URL.createObjectURL(new Blob([lines.join('\r\n')], { type: 'text/calendar' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

/** A Google Calendar "add event" link for one block (no sign-in needed). */
export function googleTemplateLink(b) {
  const q = new URLSearchParams({
    action: 'TEMPLATE', text: b.title,
    dates: `${icsStamp(b.start)}/${icsStamp(b.end)}`,
    details: `${b.description || ''}\nPlanned by Campus Copilot.`, ctz: TZ,
  })
  return `https://calendar.google.com/calendar/render?${q}`
}
