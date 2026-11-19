import React, { useCallback, useEffect, useState } from 'react'
import { GraduationCap, Loader2 } from 'lucide-react'
import api from '../../services/api'
import { useLiveEvents } from '../../hooks/useLiveEvents'

const pctText = v => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export default function LearningPanel() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const load = useCallback(() => {
    api.get('/api/admin/intelligence/learning/status')
      .then(r => { setStatus(r.data); setError('') })
      .catch(() => setError('Could not load model status.'))
  }, [])
  useEffect(load, [load])
  useLiveEvents(load, ['complaint.resolved', 'model.retrained'])

  const retrain = async (force) => {
    setBusy(true)
    setMessage('')
    try {
      const r = await api.post('/api/admin/intelligence/learning/retrain', { force })
      setMessage(r.data.promoted ? `New model ${r.data.model_version} promoted.` : `Candidate rejected: ${r.data.notes}`)
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Retraining failed.')
    } finally { setBusy(false) }
  }

  if (error) return <p role="alert" className="text-sm text-red-700">{error}</p>
  if (!status) return <div className="py-6 flex justify-center"><Loader2 className="animate-spin motion-reduce:animate-none text-teal-600" aria-label="Loading model status" /></div>

  const m = status.active_model?.metrics || {}
  const progress = Math.min(100, Math.round(100 * status.pending_training_samples / Math.max(1, status.retrain_threshold)))
  return (
    <section className="bg-white rounded-xl border border-gray-200" aria-labelledby="learning-title">
      <header className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-gray-100">
        <h3 id="learning-title" className="text-sm font-bold text-gray-900 flex items-center gap-2">
          <GraduationCap size={16} className="text-teal-600" aria-hidden="true" /> Continuous learning
        </h3>
        <span className="text-xs text-gray-500 font-mono">{status.active_model?.version || 'no model'}</span>
      </header>
      <div className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-3">
          <div>
            <div className="text-xs text-gray-500">Offline benchmark accuracy</div>
            <div className="text-2xl font-bold text-gray-900 tabular-nums">{pctText(m.benchmark_accuracy)}</div>
            <div className="text-[11px] text-gray-500">{m.benchmark_n} independent multilingual test queries; indicative only</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Verified-incident holdout</div>
            <div className="text-lg font-semibold text-gray-900 tabular-nums">{m.verified_holdout ? pctText(m.verified_holdout.accuracy) : '—'}</div>
            <div className="text-[11px] text-gray-500">{m.verified_holdout ? `${m.verified_holdout.n} held-out verified incidents` : 'Needs ≥ 5 held-out verified incidents'}</div>
          </div>
          <div className="text-[11px] text-gray-500">Historical corpus: {status.historical_index?.size?.toLocaleString()} resolved incidents · {status.historical_index?.backend}</div>
        </div>
        <div className="space-y-3">
          <div className="flex justify-between text-xs"><span className="text-gray-500">Verified incidents</span><span className="font-semibold tabular-nums">{status.verified_incidents}</span></div>
          <div className="flex justify-between text-xs"><span className="text-gray-500">Incorrect AI predictions</span><span className="font-semibold tabular-nums">{status.incorrect_predictions}</span></div>
          <div className="flex justify-between text-xs"><span className="text-gray-500">Admin correction rate</span><span className="font-semibold tabular-nums">{pctText(status.admin_correction_rate)}</span></div>
          <div>
            <div className="flex justify-between text-xs mb-1"><span className="text-gray-500">New verified samples for next retrain</span><span className="font-semibold tabular-nums">{status.pending_training_samples} / {status.retrain_threshold}</span></div>
            <div className="h-1.5 bg-gray-100 rounded-full"><div className="h-full bg-teal-600 rounded-full" style={{ width: `${progress}%` }} /></div>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <button type="button" disabled={busy || !status.retrain_ready} onClick={() => retrain(false)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50">Retrain now</button>
            <button type="button" disabled={busy || status.verified_incidents === 0} onClick={() => retrain(true)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              title="Train even below the sample threshold; promotion still requires no regression">Force retrain</button>
            {busy && <Loader2 size={16} className="animate-spin motion-reduce:animate-none text-teal-600" aria-label="Training" />}
          </div>
          {message && <p role="status" className="text-xs text-gray-700">{message}</p>}
          <p className="text-[11px] text-gray-500">Only admin-verified incidents are used. A new model is promoted only if it does not regress on the benchmark or the verified holdout.</p>
        </div>
        <div>
          <div className="text-xs font-semibold text-gray-700 mb-2">Frequently occurring new issues</div>
          {status.frequent_new_issues?.length ? (
            <ul className="space-y-1">
              {status.frequent_new_issues.map(i => (
                <li key={i.label} className="flex justify-between text-xs">
                  <span className="text-gray-800">{i.label}{!i.known_to_model && <span className="ml-1 text-amber-700">(not yet learned)</span>}</span>
                  <span className="tabular-nums text-gray-600">{i.count}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-gray-500">None yet. Issues verified outside the known taxonomy are listed here.</p>}
          <div className="text-xs font-semibold text-gray-700 mt-4 mb-2">Recent training runs</div>
          <ul className="space-y-1">
            {(status.training_runs || []).slice(0, 4).map(r => (
              <li key={r.id} className="text-[11px] text-gray-600 flex justify-between gap-2">
                <span>{new Date(r.created_at).toLocaleDateString()} · {r.trigger}</span>
                <span className={r.promoted ? 'text-emerald-700 font-semibold' : 'text-amber-700'}>{r.promoted ? 'promoted' : 'rejected'} · {pctText(r.benchmark_accuracy)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
