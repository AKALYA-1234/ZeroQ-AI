// Pure, testable pieces of the real-time client.

export const RECONNECT_BASE_MS = 1000
export const RECONNECT_MAX_MS = 15000

// Exponential backoff with "full jitter": a random delay in [base/2, cap], so a backend restart
// doesn't make every open browser reconnect in the same instant.
export function reconnectDelay(attempt, random = Math.random) {
  const cap = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempt)
  const floor = RECONNECT_BASE_MS / 2
  return Math.round(floor + random() * (cap - floor))
}

// Remembers the last `limit` event IDs; `seen(id)` returns true for a duplicate.
export function createDeduper(limit = 500) {
  const order = []
  const ids = new Set()
  return {
    seen(id) {
      if (!id) return false
      if (ids.has(id)) return true
      order.push(id)
      ids.add(id)
      if (order.length > limit) ids.delete(order.shift())
      return false
    },
    size: () => ids.size,
  }
}

// Close codes that mean "do not retry with this token".
export const UNAUTHORIZED_CLOSE = 4401

// Keep the newer of two versions of the same record (ISO timestamps compare lexicographically).
export function isStale(current, incoming) {
  return Boolean(current && incoming && current.version && incoming.version && current.version > incoming.version)
}

// Heartbeat watchdog: after a ping, a pong must arrive within this window or the socket is
// considered dead (proxies and offline networks can leave a socket "open" with nothing flowing).
export const PONG_TIMEOUT_MS = 10000

export function isConnectionStale(lastPingAt, lastPongAt, now, timeoutMs = PONG_TIMEOUT_MS) {
  if (!lastPingAt) return false                 // nothing sent yet
  if (lastPongAt >= lastPingAt) return false    // answered
  return now - lastPingAt > timeoutMs
}
