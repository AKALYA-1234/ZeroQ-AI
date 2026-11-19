import React from 'react'
import { Brain, Sparkles, ListChecks, ShieldCheck, AlertTriangle } from 'lucide-react'

// Prediction provenance must always be visible: ML vs LLM-assisted vs rules vs verified.
export const SOURCE_META = {
  ml: { label: 'ML prediction', className: 'bg-teal-50 text-teal-800 border-teal-200', Icon: Brain,
    hint: 'Trained issue classifier, supported by historical incidents' },
  llm: { label: 'LLM-assisted', className: 'bg-indigo-50 text-indigo-800 border-indigo-200', Icon: Sparkles,
    hint: 'Language-model fallback; verify before acting' },
  rules: { label: 'Rule-based', className: 'bg-amber-50 text-amber-800 border-amber-200', Icon: ListChecks,
    hint: 'Symptom rules (model unsure, no LLM configured)' },
  verified: { label: 'Admin verified', className: 'bg-emerald-50 text-emerald-800 border-emerald-200', Icon: ShieldCheck,
    hint: 'Confirmed by a quality administrator' },
  none: { label: 'No prediction', className: 'bg-gray-50 text-gray-600 border-gray-200', Icon: AlertTriangle,
    hint: 'Analysis failed' },
}

export function SourceBadge({ source }) {
  const meta = SOURCE_META[source] || SOURCE_META.none
  const { Icon } = meta
  return (
    <span title={meta.hint} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold ${meta.className}`}>
      <Icon size={12} aria-hidden="true" /> {meta.label}
    </span>
  )
}

const SEVERITY_STYLES = {
  critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700',
  medium: 'bg-amber-100 text-amber-700', low: 'bg-green-100 text-green-700',
}

export function SeverityBadge({ level }) {
  if (!level) return null
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${SEVERITY_STYLES[level] || 'bg-gray-100 text-gray-600'}`}>{level}</span>
}

export function ConfidenceMeter({ value, threshold, label = 'Confidence' }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  const tPct = threshold != null ? Math.round(threshold * 100) : null
  const ok = threshold == null || value >= threshold
  return (
    <div>
      <div className="flex items-baseline justify-between text-[11px] mb-1">
        <span className="font-semibold text-gray-600">{label}</span>
        <span className={`font-bold tabular-nums ${ok ? 'text-teal-700' : 'text-amber-700'}`}>{pct}%</span>
      </div>
      <div className="relative h-2 rounded-full bg-gray-100" role="meter" aria-label={label}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div className={`h-full rounded-full ${ok ? 'bg-teal-600' : 'bg-amber-500'}`} style={{ width: `${pct}%` }} />
        {tPct != null && (
          <div className="absolute -top-1 h-4 w-px bg-gray-500" style={{ left: `${tPct}%` }} title={`Threshold ${tPct}%`} />
        )}
      </div>
      {tPct != null && <div className="text-[10px] text-gray-500 mt-1">Threshold {tPct}% — below it the system falls back to the LLM or symptom rules</div>}
    </div>
  )
}

export function Section({ title, icon: Icon, children, action }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-gray-100">
        <h4 className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-700">
          {Icon && <Icon size={13} className="text-teal-600" aria-hidden="true" />} {title}
        </h4>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  )
}

export function Field({ label, children }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-sm text-gray-900 mt-0.5">{children || <span className="text-gray-400">—</span>}</div>
    </div>
  )
}

export function pct(v) {
  return v == null ? '—' : `${Math.round(v * 100)}%`
}
