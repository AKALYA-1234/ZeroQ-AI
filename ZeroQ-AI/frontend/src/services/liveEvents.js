// Real-time event client (single shared WebSocket per tab).
// - Authenticates with the JWT in the first message (token never goes in the URL).
// - Reconnects with capped exponential backoff plus jitter.
// - Drops duplicate events by event_id.
// - Emits a synthetic "connection.resync" event after a reconnect so views re-fetch
//   anything they may have missed while offline (the API is the source of truth).

import { reconnectDelay, createDeduper, isConnectionStale, UNAUTHORIZED_CLOSE } from './liveEventsCore'

const HEARTBEAT_MS = 15000
const WATCHDOG_MS = 5000

let socket = null
let attempts = 0
let reconnectTimer = null
let heartbeatTimer = null
let watchdogTimer = null
let lastPingAt = 0
let lastPongAt = 0
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

// Single teardown path for a socket (normal close, dead connection, or browser offline).
function dropSocket(ws, { code, retry = true } = {}) {
  if (ws.__dropped) return
  ws.__dropped = true
  clearInterval(heartbeatTimer)
  clearInterval(watchdogTimer)
  if (socket === ws) socket = null
  try { ws.close() } catch { /* already closing */ }
  // Rejected or expired token: stop retrying; the next API call will route to login.
  if (code === UNAUTHORIZED_CLOSE) { setStatus('unauthorized'); return }
  setStatus('offline')
  if (retry) scheduleReconnect()
}

function connect() {
  const token = localStorage.getItem('zeroq_token')
  if (!token || socket) return
  if (typeof navigator !== 'undefined' && navigator.onLine === false) { setStatus('offline'); return }
  setStatus('connecting')
  const ws = new WebSocket(socketUrl())
  socket = ws
  ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }))
  ws.onmessage = (msg) => {
    if (msg.data === 'pong') { lastPongAt = Date.now(); return }
    let event
    try { event = JSON.parse(msg.data) } catch { return }
    if (event.type === 'connected') {
      attempts = 0
      setStatus('live')
      if (hasConnectedBefore) emit({ type: 'connection.resync' })
      hasConnectedBefore = true
      clearInterval(heartbeatTimer)
      clearInterval(watchdogTimer)
      lastPingAt = 0
      lastPongAt = 0
      heartbeatTimer = setInterval(() => {
        if (ws.readyState === 1) { lastPingAt = Date.now(); ws.send('ping') }
      }, HEARTBEAT_MS)
      // A socket can look open while nothing flows (proxy, sleeping laptop, lost network).
      watchdogTimer = setInterval(() => {
        if (isConnectionStale(lastPingAt, lastPongAt, Date.now())) dropSocket(ws)
      }, WATCHDOG_MS)
      return
    }
    if (deduper.seen(event.event_id)) return
    emit(event)
  }
  ws.onclose = (ev) => dropSocket(ws, { code: ev.code })
  ws.onerror = () => dropSocket(ws)
}

// The browser knows about lost connectivity before TCP does: react immediately.
if (typeof window !== 'undefined') {
  window.addEventListener('offline', () => { if (socket) dropSocket(socket, { retry: false }); else setStatus('offline') })
  window.addEventListener('online', () => {
    if (handlers.size === 0) return
    clearTimeout(reconnectTimer)
    reconnectTimer = null
    attempts = 0
    connect()
  })
}

export function subscribe(handler) {
  handlers.add(handler)
  connect()
  return () => {
    handlers.delete(handler)
    if (handlers.size === 0 && socket) {
      socket.__dropped = true
      clearInterval(heartbeatTimer)
      clearInterval(watchdogTimer)
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
  clearInterval(heartbeatTimer)
  clearInterval(watchdogTimer)
  if (socket) { socket.__dropped = true; socket.close(1000) }
  socket = null
  hasConnectedBefore = false
  setStatus('idle')
}
