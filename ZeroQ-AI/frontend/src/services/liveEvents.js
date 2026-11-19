// Real-time event client (single shared WebSocket per tab).
// - Authenticates with the JWT in the first message (token never goes in the URL).
// - Reconnects with capped exponential backoff.
// - Drops duplicate events by event_id.
// - Emits a synthetic "connection.resync" event after a reconnect so views re-fetch
//   anything they may have missed while offline (the API is the source of truth).

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 15000
const HEARTBEAT_MS = 25000
const SEEN_LIMIT = 500

let socket = null
let attempts = 0
let reconnectTimer = null
let heartbeatTimer = null
let hasConnectedBefore = false
let status = 'idle'
const handlers = new Set()
const statusListeners = new Set()
const seen = []
const seenSet = new Set()

function setStatus(next) {
  status = next
  statusListeners.forEach(fn => fn(next))
}

function remember(id) {
  if (!id) return false
  if (seenSet.has(id)) return true
  seen.push(id)
  seenSet.add(id)
  if (seen.length > SEEN_LIMIT) seenSet.delete(seen.shift())
  return false
}

function emit(event) {
  handlers.forEach(fn => {
    try { fn(event) } catch (err) { console.error('live event handler failed', err) }
  })
}

function socketUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/api/ws`
}

function scheduleReconnect() {
  if (reconnectTimer || handlers.size === 0) return
  const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempts)
  attempts += 1
  reconnectTimer = setTimeout(() => { reconnectTimer = null; connect() }, delay)
}

function connect() {
  const token = localStorage.getItem('zeroq_token')
  if (!token || socket) return
  setStatus('connecting')
  const ws = new WebSocket(socketUrl())
  socket = ws
  ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }))
  ws.onmessage = (msg) => {
    if (msg.data === 'pong') return
    let event
    try { event = JSON.parse(msg.data) } catch { return }
    if (event.type === 'connected') {
      attempts = 0
      setStatus('live')
      if (hasConnectedBefore) emit({ type: 'connection.resync' })
      hasConnectedBefore = true
      clearInterval(heartbeatTimer)
      heartbeatTimer = setInterval(() => ws.readyState === 1 && ws.send('ping'), HEARTBEAT_MS)
      return
    }
    if (remember(event.event_id)) return
    emit(event)
  }
  ws.onclose = (ev) => {
    clearInterval(heartbeatTimer)
    socket = null
    if (ev.code === 4401) { setStatus('unauthorized'); return }
    setStatus('offline')
    scheduleReconnect()
  }
  ws.onerror = () => ws.close()
}

export function subscribe(handler) {
  handlers.add(handler)
  connect()
  return () => {
    handlers.delete(handler)
    if (handlers.size === 0 && socket) {
      socket.close(1000)
      socket = null
      hasConnectedBefore = false
      setStatus('idle')
    }
  }
}

export function onStatus(listener) {
  statusListeners.add(listener)
  listener(status)
  return () => statusListeners.delete(listener)
}

export function disconnect() {
  handlers.clear()
  clearTimeout(reconnectTimer)
  reconnectTimer = null
  if (socket) socket.close(1000)
  socket = null
  hasConnectedBefore = false
  setStatus('idle')
}
