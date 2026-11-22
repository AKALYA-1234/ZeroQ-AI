// Runs on Node's built-in test runner (no extra dependencies): `npm test`.
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { reconnectDelay, createDeduper, isStale, RECONNECT_BASE_MS, RECONNECT_MAX_MS } from './liveEventsCore.js'

const expect = (actual) => ({
  toBe: (expected) => assert.equal(actual, expected),
  toBeGreaterThan: (n) => assert.ok(actual > n, `${actual} > ${n}`),
})

describe('reconnectDelay', () => {
  it('grows exponentially and is capped', () => {
    const max = (a) => reconnectDelay(a, () => 1)
    expect(max(0)).toBe(RECONNECT_BASE_MS)
    expect(max(1)).toBe(2 * RECONNECT_BASE_MS)
    expect(max(3)).toBe(8 * RECONNECT_BASE_MS)
    expect(max(20)).toBe(RECONNECT_MAX_MS)
  })

  it('is jittered within [base/2, cap]', () => {
    const delays = Array.from({ length: 200 }, (_, i) => reconnectDelay(5, () => i / 199))
    expect(Math.min(...delays)).toBe(RECONNECT_BASE_MS / 2)
    expect(Math.max(...delays)).toBe(RECONNECT_MAX_MS)
    expect(new Set(delays).size).toBeGreaterThan(100)
  })
})

describe('createDeduper', () => {
  it('drops repeated event ids', () => {
    const d = createDeduper()
    expect(d.seen('a')).toBe(false)
    expect(d.seen('a')).toBe(true)
    expect(d.seen('b')).toBe(false)
  })

  it('is bounded', () => {
    const d = createDeduper(3)
    ;['a', 'b', 'c', 'd'].forEach(id => d.seen(id))
    expect(d.size()).toBe(3)
    expect(d.seen('a')).toBe(false) // evicted, treated as new
  })

  it('never treats a missing id as a duplicate', () => {
    const d = createDeduper()
    expect(d.seen(undefined)).toBe(false)
    expect(d.seen(undefined)).toBe(false)
  })
})

describe('isStale', () => {
  it('keeps the newer version of a record', () => {
    expect(isStale({ version: '2026-11-22T10:00:01' }, { version: '2026-11-22T10:00:00' })).toBe(true)
    expect(isStale({ version: '2026-11-22T10:00:00' }, { version: '2026-11-22T10:00:01' })).toBe(false)
    expect(isStale(null, { version: 'x' })).toBe(false)
  })
})

describe('isConnectionStale', async () => {
  const { isConnectionStale } = await import('./liveEventsCore.js')
  it('is fresh before any ping and once a pong answers it', () => {
    expect(isConnectionStale(0, 0, 50000)).toBe(false)
    expect(isConnectionStale(1000, 1500, 50000)).toBe(false)
  })
  it('is stale only after the timeout without a pong', () => {
    expect(isConnectionStale(1000, 0, 10999, 10000)).toBe(false)
    expect(isConnectionStale(1000, 0, 11001, 10000)).toBe(true)
  })
})
