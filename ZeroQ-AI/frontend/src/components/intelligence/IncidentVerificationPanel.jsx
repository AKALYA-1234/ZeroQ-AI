import React, { useCallback, useEffect, useState } from 'react'
import { Languages, Target, RefreshCw, ShieldCheck, AlertTriangle, Loader2, Factory } from 'lucide-react'
import api from '../../services/api'
import { useLiveEvents } from '../../hooks/useLiveEvents'
import { Section, Field, SourceBadge, SeverityBadge, ConfidenceMeter, pct } from './ui'
import { RootCauseEvidence, ResolutionEvidence, SimilarIncidents } from './IncidentEvidence'
import ResolutionForm from './ResolutionForm'

const TRANSLATION_LABEL = {
  none: 'Original is English', llm: 'Translated by LLM', glossary: 'Domain glossary (offline)',
  unavailable: 'No offline translation for this language',
}

function Understanding({ a }) {
  return (
    <Section title="Query understanding" icon={Languages}>
      <div className="space-y-3">
        <div>
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Original query</span>
            <span className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] font-semibold text-gray-700">{a.language_name || a.detected_language}</span>
            {a.is_code_mixed && <span className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] font-semibold text-gray-700">Code-mixed</span>}
          </div>
          <blockquote className="text-sm text-gray-900 bg-gray-50 border-l-2 border-gray-300 px-2.5 py-1.5 rounded-r whitespace-pre-wrap break-words">{a.original_text}</blockquote>
        </div>
        {a.translation_method !== 'none' && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1">English working text · {TRANSLATION_LABEL[a.translation_method] || a.translation_method}</div>
            <p className="text-sm text-gray-800 break-words">{a.english_text}</p>
          </div>
        )}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1">Extracted issue / symptoms</div>
          {a.symptoms?.length ? (
            <ul className="flex flex-wrap gap-1.5">
              {a.symptoms.map(s => <li key={s} className="px-2 py-0.5 rounded-full bg-teal-50 text-teal-800 text-[11px] font-medium">{s}</li>)}
            </ul>
          ) : <p className="text-xs text-gray-500">No rule-based symptoms matched.</p>}
        </div>
      </div>
    </Section>
  )
}

function Prediction({ a }) {
  return (
    <Section title="AI prediction" icon={Target} action={<SourceBadge source={a.prediction_source} />}>
      {a.is_low_confidence && (
        <p className="flex items-start gap-1.5 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-2 mb-3">
          <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
          <span><strong>Needs careful verification.</strong> {a.fallback_reason}</span>
        </p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Predicted issue">
          {a.predicted_category
            ? <>{a.predicted_category}{a.predicted_subcategory && <span className="text-gray-500"> › {a.predicted_subcategory}</span>}</>
            : <span className="text-gray-600">Undetermined — needs admin assessment</span>}
        </Field>
        <Field label="Severity / priority">
          {a.predicted_severity ? <SeverityBadge level={a.predicted_severity} /> : <span className="text-gray-600">Not assessed</span>}
        </Field>
        <Field label="Probable root cause">
          {a.predicted_root_cause || <span className="text-gray-600">Undetermined — no comparable verified incident</span>}
        </Field>
        <Field label="Affected product">{a.affected_product}</Field>
        <div className="sm:col-span-2"><Field label="Recommended action">{a.recommended_resolution}</Field></div>
      </div>
      <div className="mt-3">
        <ConfidenceMeter value={a.confidence} threshold={a.prediction_source === 'ml' || a.prediction_source === 'rules' ? a.confidence_threshold : null}
          label={a.prediction_source === 'llm' ? 'LLM self-reported confidence' : 'Model confidence'} />
      </div>
      {a.ml_result?.severity_basis?.length > 0 && (
        <details className="mt-3 text-xs text-gray-600">
          <summary className="cursor-pointer font-semibold text-gray-700">How severity was assessed</summary>
          <ul className="list-disc pl-5 mt-1 space-y-0.5">{a.ml_result.severity_basis.map(b => <li key={b}>{b}</li>)}</ul>
        </details>
      )}
      {a.prediction_source !== 'ml' && a.ml_result && (
        <p className="mt-2 text-[11px] text-gray-500">ML model's best guess: {a.ml_result.category} ({pct(a.ml_result.category_confidence)})</p>
      )}
      {a.llm_result?.reasoning && <p className="mt-2 text-[11px] text-indigo-800">LLM reasoning: {a.llm_result.reasoning}</p>}
      {a.batch_risk && (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-600">
          <Factory size={12} aria-hidden="true" /> Batch {a.batch_risk.batch_id}: XGBoost 90-day complaint risk {pct(a.batch_risk.complaint_probability)} ({a.batch_risk.risk_level})
        </p>
      )}
    </Section>
  )
}

function VerifiedResolution({ r }) {
  return (
    <Section title="Verified resolution" icon={ShieldCheck} action={<SourceBadge source="verified" />}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Confirmed issue">{r.verified_category}{r.verified_subcategory && <span className="text-gray-500"> › {r.verified_subcategory}</span>}</Field>
        <Field label="AI prediction was">
          {r.category_correct == null ? 'Not assessed' : r.category_correct
            ? <span className="text-emerald-700 font-semibold">Correct</span>
            : <span className="text-amber-700 font-semibold">Corrected ({r.predicted_category})</span>}
        </Field>
        <Field label="Root cause">{r.confirmed_root_cause}</Field>
        <Field label="Resolution">{r.resolution_action}</Field>
        <div className="sm:col-span-2"><Field label="Customer explanation">{r.admin_explanation}</Field></div>
        <Field label="Units contained">{r.units_contained}{r.units_at_risk != null && <span className="text-gray-500"> of {r.units_at_risk} at risk</span>}</Field>
        <Field label="Downtime avoided">{r.downtime_avoided_hours} h</Field>
        <Field label="Resolved by">{r.resolved_by}</Field>
        <Field label="Resolved at">{r.resolved_at && new Date(r.resolved_at).toLocaleString()}</Field>
      </div>
    </Section>
  )
}

export default function IncidentVerificationPanel({ complaintId, onResolved }) {
  const [data, setData] = useState(null)
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const res = await api.get(`/api/admin/intelligence/incidents/${complaintId}`)
      setData(res.data)
    } catch {
      setError('Could not load the AI analysis for this incident.')
    } finally {
      setLoading(false)
    }
  }, [complaintId])

  useEffect(() => { setLoading(true); setData(null); load() }, [load])
  useEffect(() => { api.get('/api/admin/intelligence/config').then(r => setConfig(r.data)).catch(() => setConfig(null)) }, [])
  useLiveEvents(ev => {
    if (ev.type === 'connection.resync' || ev.payload?.complaint_id === complaintId) load()
  }, ['analysis.completed', 'complaint.resolved', 'complaint.updated'])

  const reanalyze = async () => {
    setAnalyzing(true)
    try { await api.post(`/api/admin/intelligence/incidents/${complaintId}/analyze`); await load() }
    catch { setError('Analysis failed. Check the server logs and try again.') }
    finally { setAnalyzing(false) }
  }

  if (loading) return <div className="py-10 flex justify-center" aria-live="polite"><Loader2 className="animate-spin motion-reduce:animate-none text-teal-600" aria-label="Loading AI analysis" /></div>
  if (error && !data) return (
    <div role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between gap-2">
      {error}<button onClick={load} className="text-xs font-semibold underline">Retry</button>
    </div>
  )
  const a = data?.analysis
  const reanalyzeBtn = (
    <button type="button" onClick={reanalyze} disabled={analyzing}
      className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-700 border border-teal-200 rounded-lg px-2.5 py-1.5 hover:bg-teal-50 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500">
      <RefreshCw size={13} className={analyzing ? 'animate-spin motion-reduce:animate-none' : ''} aria-hidden="true" />
      {analyzing ? 'Analysing…' : a ? 'Re-run analysis' : 'Run AI analysis'}
    </button>
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-gray-600">Compare the AI prediction with past incidents before confirming the root cause.</p>
        {!data.resolution && reanalyzeBtn}
      </div>
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {!a ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-600">
          {data.record_type === 'customer_submitted'
            ? 'Analysis is in progress or has not run yet. It will appear here automatically.'
            : 'Historical record — run the AI analysis to compare it with similar incidents.'}
        </div>
      ) : a.status === 'failed' ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Analysis failed ({a.error}). Re-run the analysis or resolve manually below.</div>
      ) : (
        <>
          <Understanding a={a} />
          <Prediction a={a} />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            <RootCauseEvidence distribution={a.root_cause_distribution} />
            <ResolutionEvidence options={a.resolution_options} />
          </div>
          <SimilarIncidents incidents={a.similar_incidents} minSimilarity={config?.min_historical_similarity} />
        </>
      )}
      {data.resolution
        ? <VerifiedResolution r={data.resolution} />
        : <ResolutionForm complaintId={complaintId} analysis={a?.status === 'completed' ? a : null} config={config}
            expectedVersion={data.version} onStale={load}
            onResolved={() => { load(); onResolved?.() }} />}
    </div>
  )
}
