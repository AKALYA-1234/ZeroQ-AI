import React, { useState } from 'react'
import { Languages, ShieldCheck, Star, Clock, Loader2 } from 'lucide-react'
import api from '../../services/api'

const TRANSLATION_NOTE = { llm: 'translated automatically' }

export function AIUnderstandingCard({ ai, resolved = false }) {
  if (!ai) {
    return (
      <div className="bg-white rounded-xl border border-dashed border-gray-300 p-5 text-sm text-gray-600" aria-live="polite">
        Our AI is reading your complaint. This section updates automatically.
      </div>
    )
  }
  if (ai.status === 'failed') return null
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6" aria-labelledby="ai-understanding-title">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 id="ai-understanding-title" className="text-sm font-bold text-gray-900 flex items-center gap-2">
          <Languages size={16} className="text-teal-600" aria-hidden="true" /> What we understood
        </h3>
        <span className="text-[11px] font-medium text-gray-500">{resolved ? 'AI reading at submission · confirmed details above' : 'AI reading · pending review by our quality team'}</span>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-xs text-gray-500">Language detected</dt>
          <dd className="text-gray-900">{ai.language_name}{ai.is_code_mixed ? ' (mixed)' : ''}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Identified issue</dt>
          <dd className="text-gray-900">{ai.predicted_subcategory || ai.predicted_category || 'Being reviewed'}</dd>
        </div>
        {ai.symptoms?.length > 0 && (
          <div className="sm:col-span-2">
            <dt className="text-xs text-gray-500">Problems noticed</dt>
            <dd className="text-gray-900">{ai.symptoms.join(', ')}</dd>
          </div>
        )}
        {/* Glossary output is a keyword gloss, not prose — only show real translations to customers. */}
        {ai.translation_method === 'llm' && ai.english_text && (
          <div className="sm:col-span-2">
            <dt className="text-xs text-gray-500">In English ({TRANSLATION_NOTE[ai.translation_method] || 'best effort'})</dt>
            <dd className="text-gray-800">{ai.english_text}</dd>
          </div>
        )}
      </dl>
    </section>
  )
}

export function ResolutionCard({ resolution }) {
  if (!resolution) return null
  return (
    <section className="bg-white rounded-xl border-2 border-emerald-200 p-6" aria-labelledby="resolution-title">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 id="resolution-title" className="text-sm font-bold text-gray-900 flex items-center gap-2">
          <ShieldCheck size={16} className="text-emerald-600" aria-hidden="true" /> Resolved — here is what happened
        </h3>
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <Clock size={12} aria-hidden="true" /> {new Date(resolution.resolved_at).toLocaleString()}
        </span>
      </div>
      <p className="text-sm text-gray-900 leading-relaxed mb-4">{resolution.admin_explanation}</p>
      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm border-t border-gray-100 pt-4">
        <div>
          <dt className="text-xs text-gray-500">Confirmed issue</dt>
          <dd className="text-gray-900">{resolution.verified_subcategory || resolution.verified_category}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">What went wrong</dt>
          <dd className="text-gray-900">{resolution.confirmed_root_cause}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">What we did</dt>
          <dd className="text-gray-900">{resolution.resolution_action}</dd>
        </div>
      </dl>
    </section>
  )
}

export function FeedbackCard({ complaintId, feedback, onSaved }) {
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (feedback) {
    return (
      <p className="text-sm text-gray-600 bg-white rounded-xl border border-gray-200 p-4">
        Thanks for your feedback — you rated this resolution {feedback.rating}/5.
      </p>
    )
  }
  const submit = async (e) => {
    e.preventDefault()
    if (!rating) return
    setSaving(true)
    setError('')
    try {
      await api.post(`/api/complaints/${complaintId}/feedback`, { rating, comment: comment.trim() || null })
      onSaved?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your feedback.')
    } finally { setSaving(false) }
  }
  return (
    <form onSubmit={submit} className="bg-white rounded-xl border border-gray-200 p-6">
      <fieldset>
        <legend className="text-sm font-bold text-gray-900 mb-2">How satisfied are you with this resolution?</legend>
        <div className="flex gap-1" role="radiogroup" aria-label="Rating from 1 to 5">
          {[1, 2, 3, 4, 5].map(n => (
            <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? 's' : ''}`}
              onClick={() => setRating(n)}
              className="p-1.5 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500">
              <Star size={24} className={n <= rating ? 'fill-amber-400 text-amber-400' : 'text-gray-300'} aria-hidden="true" />
            </button>
          ))}
        </div>
      </fieldset>
      <label className="block mt-3">
        <span className="text-xs text-gray-600">Anything else? (optional)</span>
        <textarea rows={2} maxLength={2000} value={comment} onChange={e => setComment(e.target.value)}
          className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none" />
      </label>
      {error && <p role="alert" className="text-xs text-red-700 mt-2">{error}</p>}
      <button type="submit" disabled={!rating || saving}
        className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-semibold hover:bg-teal-700 disabled:opacity-50">
        {saving && <Loader2 size={14} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />} Send feedback
      </button>
    </form>
  )
}

export function ResolutionTimeline({ history }) {
  if (!history?.length) return null
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6" aria-labelledby="timeline-title">
      <h3 id="timeline-title" className="text-sm font-bold text-gray-900 mb-4">Timeline</h3>
      <ol className="relative border-l border-gray-200 ml-2 space-y-4">
        {history.map((h, i) => (
          <li key={`${h.status}-${h.changed_at}-${i}`} className="ml-4">
            <span className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-teal-600 ring-4 ring-white" aria-hidden="true" />
            <div className="text-xs text-gray-500">{new Date(h.changed_at).toLocaleString()}</div>
            <div className="text-sm font-medium text-gray-900 capitalize">{h.status?.replace(/_/g, ' ')}</div>
            {h.notes && <p className="text-sm text-gray-700">{h.notes}</p>}
          </li>
        ))}
      </ol>
    </section>
  )
}
