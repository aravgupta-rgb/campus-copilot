// Live voice with the Gemini Live agent over ADK's /run_live websocket.
// Mic -> 16 kHz 16-bit PCM chunks up; agent audio <- 24 kHz PCM chunks down.
import { createSession, liveUrl, VOICE_APP } from './api.js'

const WORKLET = `
class Mic extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (ch) this.port.postMessage(ch.slice(0))
    return true
  }
}
registerProcessor('cc-mic', Mic)
`

function toB64(bytes) {
  let s = ''
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000))
  return btoa(s)
}
function fromB64(b64) {
  const s = atob(b64.replace(/-/g, '+').replace(/_/g, '/'))
  const out = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i)
  return out
}

/**
 * start({ onState, onTranscript, onTool }) -> returns stop()
 * onState: 'connecting' | 'listening' | 'speaking' | 'closed' | 'error:<msg>'
 */
export async function startVoice({ onState, onTranscript, onTool }) {
  onState('connecting')
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
  const sessionId = await createSession(VOICE_APP)
  const ws = new WebSocket(liveUrl(sessionId))

  const micCtx = new AudioContext({ sampleRate: 16000 })
  const outCtx = new AudioContext({ sampleRate: 24000 })
  const workletUrl = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
  await micCtx.audioWorklet.addModule(workletUrl)
  const src = micCtx.createMediaStreamSource(stream)
  const node = new AudioWorkletNode(micCtx, 'cc-mic')
  src.connect(node)

  let pending = []
  let pendingLen = 0
  let playAt = 0
  const playing = new Set()
  let closed = false

  node.port.onmessage = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return
    pending.push(e.data); pendingLen += e.data.length
    if (pendingLen < 1600) return // ~100 ms at 16 kHz
    const pcm = new Int16Array(pendingLen)
    let o = 0
    for (const f of pending) for (let i = 0; i < f.length; i++) pcm[o++] = Math.max(-1, Math.min(1, f[i])) * 0x7fff
    pending = []; pendingLen = 0
    ws.send(JSON.stringify({ blob: { mimeType: 'audio/pcm;rate=16000', data: toB64(new Uint8Array(pcm.buffer)) } }))
  }

  const stopPlayback = () => { for (const s of playing) { try { s.stop() } catch { /* already done */ } } playing.clear(); playAt = 0 }

  ws.onopen = () => onState('listening')
  ws.onmessage = (msg) => {
    let ev
    try { ev = JSON.parse(msg.data) } catch { return }
    if (ev.interrupted) { stopPlayback(); onState('listening') }
    const tIn = ev.inputTranscription?.text
    const tOut = ev.outputTranscription?.text
    if (tIn) onTranscript('you', tIn, !!ev.partial)
    if (tOut) onTranscript('copilot', tOut, !!ev.partial)
    for (const p of ev.content?.parts || []) {
      if (p.functionResponse) onTool({ name: p.functionResponse.name, response: p.functionResponse.response || {} })
      const blob = p.inlineData
      if (blob && (blob.mimeType || '').startsWith('audio/pcm')) {
        const bytes = fromB64(blob.data)
        const i16 = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2))
        const f32 = new Float32Array(i16.length)
        for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x8000
        const buf = outCtx.createBuffer(1, f32.length, 24000)
        buf.copyToChannel(f32, 0)
        const s = outCtx.createBufferSource()
        s.buffer = buf; s.connect(outCtx.destination)
        playAt = Math.max(playAt, outCtx.currentTime + 0.02)
        s.start(playAt); playAt += buf.duration
        playing.add(s)
        onState('speaking')
        s.onended = () => { playing.delete(s); if (!playing.size && !closed) onState('listening') }
      }
    }
    if (ev.turnComplete && !playing.size) onState('listening')
  }
  ws.onerror = () => onState('error:Voice connection failed. Is the agent server running with Vertex AI?')
  ws.onclose = (e) => {
    if (!closed) onState(e.code === 1000 ? 'closed' : `error:Voice ended (${e.reason || e.code})`)
    cleanup()
  }

  function cleanup() {
    closed = true
    try { node.port.onmessage = null; src.disconnect(); node.disconnect() } catch { /* fine */ }
    stream.getTracks().forEach((t) => t.stop())
    stopPlayback()
    micCtx.close().catch(() => {}); outCtx.close().catch(() => {})
    URL.revokeObjectURL(workletUrl)
  }

  return () => {
    if (closed) return
    closed = true
    try { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ close: true })) } catch { /* fine */ }
    try { ws.close(1000) } catch { /* fine */ }
    cleanup()
    onState('closed')
  }
}
