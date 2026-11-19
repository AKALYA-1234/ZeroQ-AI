import { useEffect, useRef, useState } from 'react'
import { subscribe, onStatus } from '../services/liveEvents'

// Subscribe to real-time events. `types` limits which event types reach the handler;
// "connection.resync" is always delivered so callers can re-fetch after a reconnect.
export function useLiveEvents(handler, types) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler
  const typesKey = (types || []).join('|')

  useEffect(() => {
    const allowed = typesKey ? new Set(typesKey.split('|')) : null
    return subscribe(event => {
      if (event.type === 'connection.resync' || !allowed || allowed.has(event.type)) {
        handlerRef.current(event)
      }
    })
  }, [typesKey])
}

export function useLiveStatus() {
  const [status, setStatus] = useState('idle')
  useEffect(() => onStatus(setStatus), [])
  return status
}
