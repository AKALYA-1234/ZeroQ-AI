// Real-time event client (single shared WebSocket per tab).
// - Authenticates with the JWT in the first message (token never goes in the URL).
// - Reconnects with capped exponential backoff plus jitter.
// - Drops duplicate events by event_id.
// - Emits a synthetic "connection.resync" event after a reconnect so views re-fetch
//   anything they may have missed while offline (the API is the source of truth).

import { reconnectDelay, createDeduper, UNAUTHORIZED_CLOSE } from './liveEventsCore'

const HEARTBEAT_MS = 25000

let socket = null
let attempts = 0
let reconnectTimer = null
let heartbeatTimer = null
let hasConnectedBefore = false
let status = 'idle'
const handlers = new Set()
const statusListeners = new Set()
const deduper = createDeduper()

function setStatus(next) {
  status = next
  statusListeners.forEach(fn => fn(next))
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
  const delay = reconnectDelay(attempts)
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
    if (deduper.seen(event.event_id)) return
    emit(event)
  }
  ws.onclose = (ev) => {
    clearInterval(heartbeatTimer)
    socket = null
    // Rejected or expired token: stop retrying; the next API call will route to login.
    if (ev.code === UNAUTHORIZED_CLOSE) { setStatus('unauthorized'); return }
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
