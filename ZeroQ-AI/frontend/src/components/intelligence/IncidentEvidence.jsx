import React, { useState } from 'react'
import { GitBranch, History, Wrench } from 'lucide-react'
import { Section, pct } from './ui'

const EFFECTIVENESS_STYLES = {
  effective: 'text-emerald-700', partially_effective: 'text-amber-700',
  ineffective: 'text-red-700', pending: 'text-gray-500', admin_verified: 'text-teal-700',
}
const INITIAL_INCIDENTS = 4

export function RootCauseEvidence({ distribution }) {
  if (!distribution?.length) {
    return <Section title="Previously identified root causes" icon={GitBranch}>
      <p className="text-xs text-gray-500">No root causes recorded for similar incidents.</p>
    </Section>
  }
  return (
    <Section title="Previously identified root causes" icon={GitBranch}>
      <ul className="space-y-2">
        {distribution.map(rc => (
          <li key={rc.root_cause}>
            <div className="flex justify-between text-xs">
              <span className="text-gray-800">{rc.root_cause}</span>
              <span className="tabular-nums text-gray-600">{pct(rc.share)} · {rc.incidents} incidents</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full mt-1">
              <div className="h-full bg-teal-600 rounded-full" style={{ width: pct(rc.share) }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="text-[10px] text-gray-500 mt-2">Share weighted by similarity across the closest resolved incidents.</p>
    </Section>
  )
}

export function ResolutionEvidence({ options }) {
  return (
    <Section title="Previous resolutions & success rate" icon={Wrench}>
      {!options?.length ? <p className="text-xs text-gray-500">No corrective actions recorded for similar incidents.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-gray-500">
                <th className="py-1 pr-2 font-semibold">Action</th>
                <th className="py-1 px-2 font-semibold text-right">Used</th>
                <th className="py-1 pl-2 font-semibold text-right">Success</th>
              </tr>
            </thead>
            <tbody>
              {options.map(o => (
                <tr key={o.action} className="border-t border-gray-100 align-top">
                  <td className="py-1.5 pr-2">
                    <div className="text-gray-800">{o.action}</div>
                    {o.preventive_action && <div className="text-[10px] text-gray-500">Preventive: {o.preventive_action}</div>}
                  </td>
                  <td className="py-1.5 px-2 text-right tabular-nums">{o.uses}</td>
                  <td className="py-1.5 pl-2 text-right tabular-nums font-semibold">
                    {o.success_rate == null ? <span className="text-gray-400">n/a</span> : pct(o.success_rate)}
                    <div className="text-[10px] font-normal text-gray-500">{o.evaluated} evaluated</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-gray-500 mt-2">Success = effective 100%, partially effective 50%, ineffective 0%, from CAPA effectiveness reviews.</p>
        </div>
      )}
    </Section>
  )
}

export function SimilarIncidents({ incidents, minSimilarity = 0.2 }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? incidents : (incidents || []).slice(0, INITIAL_INCIDENTS)
  return (
    <Section title={`Similar historical incidents (${incidents?.length || 0})`} icon={History}>
      {!incidents?.length ? <p className="text-xs text-gray-500">No similar resolved incidents found — this may be a new kind of issue.</p> : (
        <>
          <ol className="divide-y divide-gray-100">
            {shown.map(inc => (
              <li key={inc.complaint_id} className="py-2 first:pt-0">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                  <span className="font-mono font-semibold text-gray-900">{inc.complaint_id}</span>
                  <span className="text-gray-500">{inc.subcategory || inc.category}</span>
                  {inc.product && <span className="text-gray-500">· {inc.product}</span>}
                  {inc.similarity < minSimilarity
                    ? <span className="ml-auto tabular-nums font-semibold text-gray-500" title="Below the similarity threshold — shown for comparison only, not used as evidence">{pct(inc.similarity)} · weak match</span>
                    : <span className="ml-auto tabular-nums font-semibold text-teal-700" title="Text similarity">{pct(inc.similarity)} match</span>}
                </div>
                <p className="text-xs text-gray-700 mt-0.5">{inc.description}</p>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5 mt-1 text-[11px]">
                  <div><dt className="inline text-gray-500">Root cause: </dt><dd className="inline text-gray-800">{inc.root_cause || '—'}{inc.root_cause_verified && <span className="text-emerald-700"> ✓</span>}</dd></div>
                  <div><dt className="inline text-gray-500">Resolution: </dt><dd className="inline text-gray-800">{inc.resolution || '—'}</dd></div>
                  <div><dt className="inline text-gray-500">Outcome: </dt><dd className={`inline capitalize ${EFFECTIVENESS_STYLES[inc.effectiveness] || 'text-gray-500'}`}>{(inc.effectiveness || 'unknown').replace(/_/g, ' ')}</dd></div>
                  <div><dt className="inline text-gray-500">Resolved: </dt><dd className="inline text-gray-800">{inc.resolved_date || '—'}</dd></div>
                </dl>
              </li>
            ))}
          </ol>
          {incidents.length > INITIAL_INCIDENTS && (
            <button type="button" onClick={() => setExpanded(v => !v)} className="mt-2 text-xs font-semibold text-teal-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 rounded">
              {expanded ? 'Show fewer' : `Show all ${incidents.length}`}
            </button>
          )}
        </>
      )}
    </Section>
  )
}
