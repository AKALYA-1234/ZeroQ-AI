import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, Info } from 'lucide-react'
import api from '../../services/api'
import { useLiveEvents, useLiveStatus } from '../../hooks/useLiveEvents'
import {
  IssueTrendChart, ResolutionTimeChart, CategoryChart, AIPerformanceChart, SatisfactionChart, WastageChart,
} from '../../components/intelligence/ImpactCharts'
import LearningPanel from '../../components/intelligence/LearningPanel'

const PRESETS = [
  { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 },
  { id: '12m', label: '12 months', days: 365 },
  { id: 'all', label: 'All time', days: null },
]
const iso = d => d.toISOString().slice(0, 10)
const num = (v, digits = 0) => (v == null ? null : Number(v).toLocaleString(undefined, { maximumFractionDigits: digits }))

const BASIS_LABEL = {
  admin_reported: 'Admin-reported', admin_estimate: 'Admin estimate', customer_reported: 'Customer-reported',
  computed: 'Computed', estimate: 'Estimate (assumption-based)',
}

function Stat({ label, value, unit, note, tone, basis }) {
  const empty = value == null
  return (
    <div className="px-4 py-3 min-w-0">
      <dt className="text-xs text-gray-500 truncate" title={label}>{label}</dt>
      <dd className={`mt-1 text-2xl font-bold tabular-nums ${empty ? 'text-gray-400' : 'text-gray-900'}`}>
        {empty ? <span title="Not available — no supporting data">N/A</span> : value}
        {!empty && unit && <span className="text-sm font-semibold text-gray-500 ml-0.5">{unit}</span>}
      </dd>
      {basis && <dd className="text-[10px] uppercase tracking-wide text-gray-400 mt-0.5">{BASIS_LABEL[basis] || basis}</dd>}
      {note && <dd className={`text-[11px] mt-0.5 ${tone === 'good' ? 'text-emerald-700' : tone === 'bad' ? 'text-red-700' : 'text-gray-500'}`}>{note}</dd>}
    </div>
  )
}

function StatGroup({ title, caption, children }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200" aria-label={title}>
      <header className="px-4 pt-3">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-teal-700">{title}</h3>
        {caption && <p className="text-[11px] text-gray-500">{caption}</p>}
      </header>
      <dl className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 divide-gray-100 [&>*]:border-gray-100 [&>*]:border-t md:[&>*]:border-l">{children}</dl>
    </section>
  )
}

function changeNote(pct, lowerIsBetter, suffix = 'vs prior period') {
  if (pct == null) return { note: 'No prior-period data' }
  const better = lowerIsBetter ? pct < 0 : pct > 0
  return { note: `${pct > 0 ? '+' : ''}${pct}% ${suffix}`, tone: pct === 0 ? undefined : better ? 'good' : 'bad' }
}

export default function AIImpactAnalytics() {
  const [preset, setPreset] = useState('12m')
  const [custom, setCustom] = useState({ start: '', end: '' })
  const [category, setCategory] = useState('')
  const [scope, setScope] = useState('live')
  const [llmStatus, setLlmStatus] = useState(null)
  const [categories, setCategories] = useState([])
  const [kpis, setKpis] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const live = useLiveStatus()

  const range = useMemo(() => {
    if (preset === 'custom') return { start: custom.start || undefined, end: custom.end || undefined }
    const p = PRESETS.find(x => x.id === preset)
    if (!p?.days) return {}
    const end = new Date()
    return { start: iso(new Date(end.getTime() - p.days * 86400000)), end: iso(end) }
  }, [preset, custom])

  const load = useCallback(async () => {
    setError('')
    const params = { ...range, scope, ...(category ? { category } : {}) }
    try {
      const [k, t] = await Promise.all([
        api.get('/api/admin/intelligence/kpis', { params }),
        api.get('/api/admin/intelligence/trends', { params }),
      ])
      setKpis(k.data)
      setTrends(t.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load analytics.')
    } finally { setLoading(false) }
  }, [range, category, scope])

  useEffect(() => { setLoading(true); load() }, [load])
  useEffect(() => { api.get('/api/admin/intelligence/config').then(r => setCategories(r.data.categories || [])).catch(() => {}) }, [])
  useEffect(() => { api.get('/api/admin/intelligence/llm/status').then(r => setLlmStatus(r.data)).catch(() => setLlmStatus(null)) }, [])
  useLiveEvents(() => load(), ['complaint.resolved', 'analysis.completed', 'feedback.submitted'])

  const im = kpis?.issue_management || {}
  const ai = kpis?.ai_performance || {}
  const bi = kpis?.business_impact || {}
  const resTime = changeNote(im.avg_resolution_days_change_pct, true)
  const sample = bi.repeat_sample || {}
  const repeat = bi.repeat_incident_reduction_pct == null
    ? { note: `Needs ≥ ${sample.minimum} complaints per period (now ${sample.current ?? 0} / prior ${sample.prior ?? 0})` }
    : { note: `Repeat rate ${bi.repeat_incident_rate_prior_pct}% → ${bi.repeat_incident_rate_pct}%`, tone: bi.repeat_incident_reduction_pct > 0 ? 'good' : 'bad' }

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">AI Insights & Impact</h1>
          <p className="text-sm text-gray-500">Every figure is computed from live complaint, prediction, resolution and feedback records.</p>
        </div>
        <p className="text-xs text-gray-500 flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${live === 'live' ? 'bg-emerald-500' : 'bg-gray-300'}`} aria-hidden="true" />
          {live === 'live' ? 'Live' : live === 'offline' ? 'Offline — showing last loaded data' : 'Connecting…'}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-3 flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Date range" className="flex flex-wrap gap-1">
          {[...PRESETS, { id: 'custom', label: 'Custom' }].map(p => (
            <button key={p.id} type="button" aria-pressed={preset === p.id} onClick={() => setPreset(p.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${preset === p.id ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
              {p.label}
            </button>
          ))}
        </div>
        {preset === 'custom' && (
          <div className="flex flex-wrap gap-2">
            <label className="text-xs text-gray-600">From
              <input type="date" value={custom.start} onChange={e => setCustom(c => ({ ...c, start: e.target.value }))} className="block mt-0.5 border border-gray-300 rounded-lg px-2 py-1 text-sm" />
            </label>
            <label className="text-xs text-gray-600">To
              <input type="date" value={custom.end} onChange={e => setCustom(c => ({ ...c, end: e.target.value }))} className="block mt-0.5 border border-gray-300 rounded-lg px-2 py-1 text-sm" />
            </label>
          </div>
        )}
        <label className="text-xs text-gray-600 sm:ml-auto">Data
          <select value={scope} onChange={e => setScope(e.target.value)} className="block mt-0.5 border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white">
            <option value="live">Live platform data</option>
            <option value="imported">Imported historical dataset</option>
            <option value="all">Both</option>
          </select>
        </label>
        <label className="text-xs text-gray-600">Category
          <select value={category} onChange={e => setCategory(e.target.value)} className="block mt-0.5 border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white min-w-[12rem]">
            <option value="">All categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>

      {scope !== 'live' && (
        <p role="note" className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Includes the imported historical dataset (synthetic records loaded at setup). These figures are not live production results.
        </p>
      )}
      {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>}
      {loading && !kpis ? (
        <div className="py-16 flex justify-center"><Loader2 className="animate-spin motion-reduce:animate-none text-teal-600" aria-label="Loading analytics" /></div>
      ) : kpis && (
        <>
          <StatGroup title="Issue management" caption={`${kpis.window.start.slice(0, 10)} → ${kpis.window.end.slice(0, 10)}`}>
            <Stat label="Queries received" value={num(im.total_queries)} />
            <Stat label="Issues identified" value={num(im.issues_identified)} />
            <Stat label="Issues resolved" value={num(im.issues_resolved)} />
            <Stat label="Pending issues" value={num(im.pending_issues)} />
            <Stat label="Avg resolution time"
              value={im.avg_resolution_days != null && im.avg_resolution_days < 1 ? num(im.avg_resolution_days * 24, 1) : num(im.avg_resolution_days, 1)}
              unit={im.avg_resolution_days != null && im.avg_resolution_days < 1 ? ' h' : ' days'}
              {...(im.resolution_time_sample ? { ...resTime, note: `${resTime.note} · n=${im.resolution_time_sample}` } : { note: 'No recorded resolution durations' })} />
            <Stat label="Resolution rate" value={num(im.resolution_rate_pct, 1)} unit="%" />
          </StatGroup>

          <StatGroup title="AI performance" caption="Accuracy uses admin-verified incidents only">
            <Stat label="Prediction accuracy" value={num(ai.prediction_accuracy_pct, 1)} unit="%"
              note={ai.verified_predictions ? `${ai.verified_predictions} verified` : 'No verified predictions yet'} />
            <Stat label="ML predictions" value={num(ai.ml_prediction_count)} note={`of ${num(ai.predictions_total)} total`} />
            <Stat label="LLM fallbacks" value={num(ai.llm_fallback_count)}
              note={llmStatus && !llmStatus.configured ? 'LLM not configured' : `Rules: ${num(ai.rules_fallback_count)} · Undetermined: ${num(ai.undetermined_count)}`} />
            <Stat label="Low-confidence" value={num(ai.low_confidence_count)} />
            <Stat label="Admin correction rate" value={num(ai.admin_correction_rate_pct, 1)} unit="%" />
            <Stat label="Offline benchmark" value={num(ai.offline_benchmark_accuracy_pct, 1)} unit="%"
              note={ai.offline_benchmark_n ? `Independent test set, n=${ai.offline_benchmark_n}` : 'Independent test set'} />
          </StatGroup>

          <StatGroup title="Business impact" caption="Admin-recorded figures and documented assumptions — nothing is estimated silently">
            <Stat label="Products saved" value={num(bi.products_saved_units)} unit=" units" basis={bi.metric_basis?.products_saved_units} />
            <Stat label="Wastage reduction" value={num(bi.wastage_reduction_pct, 1)} unit="%" basis={bi.metric_basis?.wastage_reduction_pct}
              note={bi.wastage_sample ? `Contained ÷ at-risk, ${bi.wastage_sample} incidents` : 'No at-risk units recorded'} />
            <Stat label="Est. cost saved" value={bi.estimated_cost_saved_inr == null ? null : `₹${num(bi.estimated_cost_saved_inr)}`}
              basis={bi.metric_basis?.estimated_cost_saved_inr}
              note={bi.estimated_cost_saved_inr == null ? 'Unit costs not configured' : undefined} />
            <Stat label="Downtime avoided" value={num(bi.downtime_avoided_hours, 1)} unit=" h" basis={bi.metric_basis?.downtime_avoided_hours} />
            <Stat label="Customer satisfaction" value={num(bi.customer_satisfaction_pct, 1)} unit="%" basis={bi.metric_basis?.customer_satisfaction_pct}
              note={bi.feedback_count ? `${bi.feedback_count} ratings · avg ${bi.avg_rating}/5` : 'No ratings yet'} />
            <Stat label="Repeat incident reduction" value={num(bi.repeat_incident_reduction_pct, 1)} unit="%"
              basis={bi.metric_basis?.repeat_incident_reduction_pct} {...repeat} />
          </StatGroup>

          {trends && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <IssueTrendChart data={trends.issues} granularity={trends.granularity} />
              <CategoryChart data={trends.category_distribution} />
              <ResolutionTimeChart data={trends.issues} granularity={trends.granularity} />
              <AIPerformanceChart data={trends.ai_performance} />
              <WastageChart data={trends.wastage} />
              <SatisfactionChart data={trends.customer_satisfaction} />
            </div>
          )}

          <LearningPanel />

          <details className="bg-white rounded-xl border border-gray-200 p-4">
            <summary className="cursor-pointer text-sm font-bold text-gray-900 flex items-center gap-2">
              <Info size={15} className="text-teal-600" aria-hidden="true" /> Metric definitions & business assumptions
            </summary>
            <dl className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
              {kpis.assumptions.map(a => (
                <div key={a.metric}>
                  <dt className="text-xs font-semibold text-gray-800">{a.metric}</dt>
                  <dd className="text-xs text-gray-600">{a.definition}</dd>
                </div>
              ))}
            </dl>
          </details>
        </>
      )}
    </div>
  )
}
