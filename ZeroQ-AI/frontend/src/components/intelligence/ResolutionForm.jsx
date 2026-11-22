import React, { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import api from '../../services/api'
import { Section } from './ui'

const NEW_SUB = '__new__'
const inputCls = 'w-full text-sm border border-gray-300 rounded-lg px-2.5 py-2 bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-teal-500'

function initialForm(analysis) {
  return {
    verified_category: analysis?.predicted_category || '',
    verified_subcategory: analysis?.predicted_subcategory || '',
    custom_subcategory: '',
    confirmed_root_cause: analysis?.predicted_root_cause || '',
    resolution_action: analysis?.recommended_resolution || '',
    admin_explanation: '',
    units_contained: 0,
    units_at_risk: '',
    downtime_avoided_hours: 0,
  }
}

export default function ResolutionForm({ complaintId, analysis, config, expectedVersion, onResolved, onStale }) {
  const [form, setForm] = useState(() => initialForm(analysis))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setForm(initialForm(analysis)) }, [analysis?.id, analysis?.updated_at])

  const subOptions = useMemo(() => Object.entries(config?.subcategories || {})
    .filter(([, cat]) => cat === form.verified_category).map(([sub]) => sub), [config, form.verified_category])
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))
  const correcting = analysis && form.verified_category && form.verified_category !== analysis.predicted_category
  const rootCauses = (analysis?.root_cause_distribution || []).map(r => r.root_cause)
  const actions = (analysis?.resolution_options || []).map(r => r.action)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    const sub = form.verified_subcategory === NEW_SUB ? form.custom_subcategory.trim() : form.verified_subcategory
    try {
      const res = await api.post(`/api/admin/intelligence/incidents/${complaintId}/resolve`, {
        verified_category: form.verified_category,
        verified_subcategory: sub || null,
        confirmed_root_cause: form.confirmed_root_cause,
        resolution_action: form.resolution_action,
        admin_explanation: form.admin_explanation,
        units_contained: Number(form.units_contained) || 0,
        units_at_risk: form.units_at_risk === '' ? null : Number(form.units_at_risk),
        downtime_avoided_hours: Number(form.downtime_avoided_hours) || 0,
        expected_version: expectedVersion || null,
      })
      onResolved?.(res.data)
    } catch (err) {
      if (err.response?.status === 409) onStale?.()   // someone else changed or resolved it: reload
      const detail = err.response?.data?.detail
      setError(Array.isArray(detail) ? detail.map(d => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ') : (detail || 'Could not resolve the incident. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Section title="Verify & resolve" icon={CheckCircle2}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">Confirmed category *</span>
            <select required className={inputCls} value={form.verified_category}
              onChange={e => setForm(f => ({ ...f, verified_category: e.target.value, verified_subcategory: '' }))}>
              <option value="">Select category</option>
              {(config?.categories || []).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">Subcategory</span>
            <select className={inputCls} value={form.verified_subcategory} onChange={set('verified_subcategory')}>
              <option value="">Not specified</option>
              {subOptions.map(s => <option key={s} value={s}>{s}</option>)}
              {form.verified_subcategory && form.verified_subcategory !== NEW_SUB && !subOptions.includes(form.verified_subcategory) &&
                <option value={form.verified_subcategory}>{form.verified_subcategory}</option>}
              <option value={NEW_SUB}>New subcategory…</option>
            </select>
          </label>
        </div>
        {form.verified_subcategory === NEW_SUB && (
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">New subcategory name</span>
            <input className={inputCls} maxLength={120} value={form.custom_subcategory} onChange={set('custom_subcategory')} />
          </label>
        )}
        {correcting && (
          <p className="flex items-start gap-1.5 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-2">
            <AlertCircle size={14} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
            You are correcting the AI prediction ({analysis.predicted_category}). The correction is stored as verified training feedback.
          </p>
        )}
        <label className="block">
          <span className="text-[11px] font-semibold text-gray-600">Actual root cause *</span>
          <input required list="rc-options" className={inputCls} maxLength={2000} value={form.confirmed_root_cause} onChange={set('confirmed_root_cause')} />
          <datalist id="rc-options">{rootCauses.map(r => <option key={r} value={r} />)}</datalist>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold text-gray-600">Resolution performed *</span>
          <input required list="action-options" className={inputCls} maxLength={2000} value={form.resolution_action} onChange={set('resolution_action')} />
          <datalist id="action-options">{actions.map(a => <option key={a} value={a} />)}</datalist>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold text-gray-600">Explanation for the customer * <span className="font-normal text-gray-500">(shown on their dashboard)</span></span>
          <textarea required rows={3} minLength={10} maxLength={4000} className={`${inputCls} resize-y`} value={form.admin_explanation} onChange={set('admin_explanation')}
            placeholder="What went wrong, what we did about it, and what happens next." />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">Units contained / saved from wastage</span>
            <input type="number" min={0} step={1} inputMode="numeric" className={inputCls} value={form.units_contained} onChange={set('units_contained')} />
          </label>
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">Units at risk (affected lot)</span>
            <input type="number" min={0} step={1} inputMode="numeric" placeholder="Unknown" className={inputCls} value={form.units_at_risk} onChange={set('units_at_risk')} />
          </label>
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600">Production downtime avoided (hours)</span>
            <input type="number" min={0} step={0.5} inputMode="decimal" className={inputCls} value={form.downtime_avoided_hours} onChange={set('downtime_avoided_hours')} />
          </label>
        </div>
        <p className="text-[10px] text-gray-500">Impact figures feed the business-impact dashboard as admin-reported values. Leave "units at risk" empty if unknown — wastage % is then shown as N/A, never estimated.</p>
        {error && <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-2.5 py-2">{error}</p>}
        <button type="submit" disabled={saving || !form.verified_category || !form.confirmed_root_cause.trim() || !form.resolution_action.trim() || form.admin_explanation.trim().length < 10}
          className="inline-flex items-center gap-2 bg-teal-600 text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2">
          {saving ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <CheckCircle2 size={15} aria-hidden="true" />}
          {saving ? 'Resolving…' : 'Mark resolved & notify customer'}
        </button>
      </form>
    </Section>
  )
}
