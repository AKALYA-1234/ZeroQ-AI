import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, Loader2, ShieldAlert, ShieldCheck } from 'lucide-react'
import api from '../../services/api'
import { useLiveEvents, useLiveStatus } from '../../hooks/useLiveEvents'
import { Section, Stat, StatGroup } from '../../components/intelligence/ui'

const PRESETS = [
  { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 },
  { id: 'all', label: 'All time', days: null },
]
const SCOPES = [
  { id: 'live', label: 'Real customers (live)' },
  { id: 'test', label: 'Test accounts' },
  { id: 'imported', label: 'Imported synthetic data' },
  { id: 'all', label: 'Everything' },
]
const iso = d => d.toISOString().slice(0, 10)
const fmt = (v, digits = 1) => (v == null ? null : Number(v).toFixed(digits))

function rateNote(r) {
  if (!r || r.n === 0) return 'No data'
  const ci = r.ci95_pct ? `95% CI ${r.ci95_pct[0]}–${r.ci95_pct[1]}% · ` : ''
  return `${ci}n=${r.n}${r.reliable ? '' : ' · too few to rely on'}`
}

function RateTable({ title, rows, labelKey, labelHeader }) {
  return (
    <Section title={title}>
      {!rows?.length ? <p className="text-xs text-gray-500">No verified incidents yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-gray-500">
                <th className="py-1 pr-2 font-semibold">{labelHeader}</th>
                <th className="py-1 px-2 font-semibold text-right">Accuracy</th>
                <th className="py-1 pl-2 font-semibold text-right">n</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r[labelKey]} className="border-t border-gray-100">
                  <td className="py-1.5 pr-2 text-gray-800">{r[labelKey]}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums font-semibold">
                    {fmt(r.value_pct) == null ? 'N/A' : `${fmt(r.value_pct)}%`}
                    {!r.reliable && <span className="ml-1 font-normal text-amber-700" title="Fewer than 5 incidents">⚠</span>}
                  </td>
                  <td className="py-1.5 pl-2 text-right tabular-nums text-gray-600">{r.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

function ConfusionMatrix({ cm }) {
  if (!cm?.labels?.length) return null
  const max = Math.max(1, ...cm.matrix.flat())
  const short = l => (l.length > 14 ? `${l.slice(0, 13)}…` : l)
  return (
    <Section title="Confusion matrix (rows: verified, columns: predicted)">
      <div className="overflow-x-auto">
        <table className="text-[11px] border-collapse">
          <thead>
            <tr><th className="p-1" />{cm.labels.map(l => <th key={l} className="p-1 font-medium text-gray-600 align-bottom" title={l}>{short(l)}</th>)}</tr>
          </thead>
          <tbody>
            {cm.labels.map((row, i) => (
              <tr key={row}>
                <th className="p-1 pr-2 text-right font-medium text-gray-600 whitespace-nowrap" title={row}>{short(row)}</th>
                {cm.matrix[i].map((n, j) => (
                  <td key={j} className={`p-1 text-center tabular-nums min-w-[2.2rem] border border-gray-100 ${i === j ? 'font-bold' : ''}`}
                    style={{ backgroundColor: n ? `rgba(13,148,136,${0.12 + 0.6 * n / max})` : undefined,
                             color: n && n / max > 0.6 ? '#fff' : undefined }}>{n || ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

export default function AIMonitoring() {
  const [scope, setScope] = useState('live')
  const [preset, setPreset] = useState('all')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const live = useLiveStatus()

  const range = useMemo(() => {
    const p = PRESETS.find(x => x.id === preset)
    if (!p?.days) return {}
    const end = new Date()
    return { start: iso(new Date(end.getTime() - p.days * 86400000)), end: iso(end) }
  }, [preset])

  const load = useCallback(async () => {
    setError('')
    try {
      const res = await api.get('/api/admin/intelligence/monitoring', { params: { ...range, scope } })
      setData(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load monitoring data.')
    } finally { setLoading(false) }
  }, [range, scope])

  useEffect(() => { setLoading(true); load() }, [load])
  useLiveEvents(() => load(), ['complaint.resolved', 'analysis.completed'])

  const downloadReport = async () => {
    try {
      const res = await api.get('/api/admin/intelligence/monitoring/report', { params: { ...range, scope }, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `zeroq-monitoring-${scope}-${iso(new Date())}.md`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch { window.alert('Could not generate the report.') }
  }

  const b = data?.basis
  const acc = data?.accuracy
  const pipe = data?.pipeline
  const corr = data?.corrections
  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Model Monitoring</h1>
          <p className="text-sm text-gray-500">Real-world prediction quality, measured only against admin-verified incidents.</p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-gray-500 flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${live === 'live' ? 'bg-emerald-500' : 'bg-gray-300'}`} aria-hidden="true" />
            {live === 'live' ? 'Live' : live === 'offline' ? 'Offline' : 'Connecting…'}
          </p>
          <button type="button" onClick={downloadReport}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-700 border border-teal-200 rounded-lg px-3 py-1.5 hover:bg-teal-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500">
            <Download size={13} aria-hidden="true" /> Download report
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-3 flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Date range" className="flex gap-1">
          {PRESETS.map(p => (
            <button key={p.id} type="button" aria-pressed={preset === p.id} onClick={() => setPreset(p.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${preset === p.id ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>{p.label}</button>
          ))}
        </div>
        <label className="text-xs text-gray-600 sm:ml-auto">Data
          <select value={scope} onChange={e => setScope(e.target.value)} className="block mt-0.5 border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white">
            {SCOPES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
      </div>

      {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>}
      {loading && !data ? (
        <div className="py-16 flex justify-center"><Loader2 className="animate-spin motion-reduce:animate-none text-teal-600" aria-label="Loading monitoring" /></div>
      ) : data && (
        <>
          <div role="note" className={`flex items-start gap-2 text-xs rounded-lg border px-3 py-2 ${scope !== 'live' || !b.sample_sufficient ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-emerald-50 border-emerald-200 text-emerald-900'}`}>
            {scope !== 'live' || !b.sample_sufficient ? <ShieldAlert size={15} className="mt-0.5 flex-shrink-0" aria-hidden="true" /> : <ShieldCheck size={15} className="mt-0.5 flex-shrink-0" aria-hidden="true" />}
            <span>{b.statement} <strong>{b.verified_incidents}</strong> verified incidents, <strong>{b.predictions_assessed}</strong> with a predicted category.</span>
          </div>

          <StatGroup title="Real-world accuracy" caption="Admin-verified category vs the AI's final prediction">
            <Stat label="Category accuracy" value={fmt(acc.category.value_pct)} unit="%" note={rateNote(acc.category)} tone={acc.category.reliable ? undefined : 'bad'} />
            <Stat label="Incorrect predictions" value={fmt(acc.incorrect_prediction_rate_pct)} unit="%" />
            <Stat label="Admin correction rate" value={fmt(corr.any_correction.value_pct)} unit="%" note={rateNote(corr.any_correction)} />
            <Stat label="Prediction coverage" value={fmt(acc.coverage_pct)} unit="%" note="Incidents where a category was proposed" />
            <Stat label="Root cause matched" value={fmt(corr.root_cause_correct.value_pct)} unit="%" note={rateNote(corr.root_cause_correct)} />
            <Stat label="Verified incidents" value={b.verified_incidents} />
          </StatGroup>

          <StatGroup title="Pipeline health" caption="All analyses in scope, verified or not">
            <Stat label="Analyses" value={pipe.analyses_total} />
            <Stat label="Low-confidence" value={fmt(pipe.low_confidence_rate_pct)} unit="%" />
            <Stat label="LLM fallback" value={fmt(pipe.llm_fallback_rate_pct)} unit="%"
              note={Object.keys(pipe.llm_providers || {}).length ? Object.entries(pipe.llm_providers).map(([k, v]) => `${k}: ${v}`).join(' · ') : undefined} />
            <Stat label="Rule-based" value={fmt(pipe.rules_fallback_rate_pct)} unit="%" />
            <Stat label="Undetermined" value={fmt(pipe.undetermined_rate_pct)} unit="%" />
            <Stat label="Failed analyses" value={pipe.failed_analyses} tone={pipe.failed_analyses ? 'bad' : undefined} />
          </StatGroup>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Section title="Precision & recall by category">
              {!Object.keys(data.per_category).length ? <p className="text-xs text-gray-500">No verified incidents yet.</p> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-[10px] uppercase tracking-wide text-gray-500">
                        <th className="py-1 pr-2 font-semibold">Category</th>
                        <th className="py-1 px-2 font-semibold text-right">Precision</th>
                        <th className="py-1 px-2 font-semibold text-right">Recall</th>
                        <th className="py-1 px-2 font-semibold text-right">F1</th>
                        <th className="py-1 pl-2 font-semibold text-right">Support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.per_category).sort((x, y) => y[1].support - x[1].support).map(([label, m]) => (
                        <tr key={label} className="border-t border-gray-100">
                          <td className="py-1.5 pr-2 text-gray-800">{label}</td>
                          <td className="py-1.5 px-2 text-right tabular-nums">{m.precision.toFixed(2)}</td>
                          <td className="py-1.5 px-2 text-right tabular-nums">{m.recall.toFixed(2)}</td>
                          <td className="py-1.5 px-2 text-right tabular-nums">{m.f1.toFixed(2)}</td>
                          <td className="py-1.5 pl-2 text-right tabular-nums">{m.support}{m.low_sample && <span className="ml-1 text-amber-700" title="Fewer than 5 incidents">⚠</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>
            <RateTable title="Accuracy by language" rows={data.by_language} labelKey="language" labelHeader="Language" />
            <RateTable title="Accuracy by prediction source"
              rows={Object.entries(data.by_source).map(([k, v]) => ({ source: k === 'ml' ? 'ML model' : k === 'llm' ? 'LLM-assisted' : 'Rule-based', ...v }))}
              labelKey="source" labelHeader="Source" />
            <RateTable title="Accuracy by model version" rows={data.by_model_version} labelKey="model_version" labelHeader="Model version" />
          </div>

          <Section title="Model vs fallback on the same verified incidents">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              {[['ML best guess (all verified incidents)', data.model_vs_fallback.ml_best_guess_on_all_verified],
                ['LLM, when it was used', data.model_vs_fallback.llm_when_used]].map(([label, r]) => (
                <div key={label}>
                  <dt className="text-xs text-gray-500">{label}</dt>
                  <dd className="text-lg font-bold tabular-nums text-gray-900">{fmt(r.value_pct) == null ? 'N/A' : `${fmt(r.value_pct)}%`}</dd>
                  <dd className="text-[11px] text-gray-500">{rateNote(r)}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title="New and unfamiliar issues">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              {[['Verified new issue types', data.unfamiliar.verified_new_issue_types],
                ['LLM-proposed, outside the taxonomy', data.unfamiliar.llm_proposed_unknown_subcategories]].map(([title, items]) => (
                <div key={title}>
                  <div className="font-semibold text-gray-700 mb-1">{title}</div>
                  {items.length ? <ul className="space-y-0.5">{items.map(i => <li key={i.label} className="flex justify-between"><span>{i.label}</span><span className="tabular-nums text-gray-600">{i.count}</span></li>)}</ul>
                    : <p className="text-gray-500">None yet.</p>}
                </div>
              ))}
              <div>
                <div className="font-semibold text-gray-700 mb-1">Counts</div>
                <p className="text-gray-600">Analyses flagged unfamiliar: <strong>{data.unfamiliar.analyses_flagged_unfamiliar}</strong></p>
                <p className="text-gray-600">Left undetermined (verified): <strong>{data.unfamiliar.undetermined_verified}</strong></p>
              </div>
            </div>
          </Section>

          <ConfusionMatrix cm={data.confusion_matrix} />

          {data.calibration && (
            <Section title="Confidence calibration (verified outcomes)">
              <p className="text-xs text-gray-600 mb-2">ECE {data.calibration.ece} · Brier {data.calibration.brier}. A well-calibrated model is correct about as often as it says.</p>
              <div className="overflow-x-auto">
                <table className="text-xs">
                  <thead><tr className="text-[10px] uppercase tracking-wide text-gray-500 text-left"><th className="pr-4">Confidence</th><th className="pr-4 text-right">n</th><th className="pr-4 text-right">Mean confidence</th><th className="text-right">Actual accuracy</th></tr></thead>
                  <tbody>{data.calibration.reliability.map(r => (
                    <tr key={r.bin} className="border-t border-gray-100"><td className="pr-4 py-1">{r.bin}</td><td className="pr-4 text-right tabular-nums">{r.n}</td><td className="pr-4 text-right tabular-nums">{(r.mean_confidence * 100).toFixed(0)}%</td><td className="text-right tabular-nums font-semibold">{(r.accuracy * 100).toFixed(0)}%</td></tr>))}</tbody>
                </table>
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  )
}
