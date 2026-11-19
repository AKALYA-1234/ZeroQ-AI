import React from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, ComposedChart, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'

// Palette follows the existing analytics pages; source colours match the provenance badges.
const C = { teal: '#0d9488', tealLight: '#5eead4', indigo: '#6366f1', amber: '#f59e0b', slate: '#64748b', grid: '#f0f0f0' }
const AXIS = { fontSize: 11, fill: '#6b7280' }
const TOOLTIP = { contentStyle: { fontSize: 12, borderRadius: 8, borderColor: '#e5e7eb' } }

function ChartPanel({ title, subtitle, empty, children, height = 240 }) {
  return (
    <figure className="bg-white rounded-xl border border-gray-200 p-4 min-w-0">
      <figcaption className="mb-3">
        <div className="text-sm font-bold text-gray-900">{title}</div>
        {subtitle && <div className="text-xs text-gray-500 mt-0.5">{subtitle}</div>}
      </figcaption>
      {empty ? (
        <div className="flex items-center justify-center text-center text-xs text-gray-500 border border-dashed border-gray-200 rounded-lg px-4" style={{ height }}>
          {empty}
        </div>
      ) : <div style={{ height }}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>}
    </figure>
  )
}

export function IssueTrendChart({ data, granularity }) {
  return (
    <ChartPanel title="Issues received vs resolved" subtitle={`Per ${granularity}`} empty={!data?.length && 'No complaints in this period.'}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
        <XAxis dataKey="period" tick={AXIS} minTickGap={16} />
        <YAxis tick={AXIS} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="received" name="Received" stroke={C.slate} strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="resolved" name="Resolved" stroke={C.teal} strokeWidth={2} dot={false} />
      </LineChart>
    </ChartPanel>
  )
}

export function ResolutionTimeChart({ data, granularity }) {
  const rows = (data || []).filter(d => d.avg_resolution_days != null)
  return (
    <ChartPanel title="Average resolution time" subtitle={`Days from submission to resolution, per ${granularity}`} empty={!rows.length && 'No complaints with a recorded resolution duration in this period (imported historical records do not carry one).'}>
      <LineChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
        <XAxis dataKey="period" tick={AXIS} minTickGap={16} />
        <YAxis tick={AXIS} />
        <Tooltip {...TOOLTIP} formatter={v => [`${v} days`, 'Avg resolution']} />
        <Line type="monotone" dataKey="avg_resolution_days" stroke={C.teal} strokeWidth={2} dot={false} />
      </LineChart>
    </ChartPanel>
  )
}

export function CategoryChart({ data }) {
  return (
    <ChartPanel title="Issue category distribution" subtitle="Complaints received in this period" empty={!data?.length && 'No categorised complaints.'} height={280}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} horizontal={false} />
        <XAxis type="number" tick={AXIS} allowDecimals={false} />
        <YAxis type="category" dataKey="category" tick={{ ...AXIS, fontSize: 10 }} width={150} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey="count" name="Complaints" fill={C.teal} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ChartPanel>
  )
}

export function AIPerformanceChart({ data }) {
  return (
    <ChartPanel title="AI predictions by source" subtitle="Bars: predictions made · line: verified accuracy %"
      empty={!data?.length && 'No AI predictions in this period yet. They appear as customers submit complaints.'}>
      <ComposedChart data={data} margin={{ top: 4, right: 0, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
        <XAxis dataKey="period" tick={AXIS} />
        <YAxis yAxisId="n" tick={AXIS} allowDecimals={false} />
        <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={AXIS} unit="%" />
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar yAxisId="n" dataKey="ml" name="ML" stackId="s" fill={C.teal} maxBarSize={56} />
        <Bar yAxisId="n" dataKey="llm" name="LLM-assisted" stackId="s" fill={C.indigo} />
        <Bar yAxisId="n" dataKey="rules" name="Rule-based" stackId="s" fill={C.amber} radius={[4, 4, 0, 0]} />
        <Line yAxisId="pct" type="monotone" dataKey="accuracy_pct" name="Verified accuracy" stroke="#111827" strokeWidth={2} connectNulls />
      </ComposedChart>
    </ChartPanel>
  )
}

export function SatisfactionChart({ data }) {
  return (
    <ChartPanel title="Customer satisfaction" subtitle="Share of resolution ratings ≥ 4 / 5"
      empty={!data?.length && 'No customer ratings yet. Customers can rate each resolution from their dashboard.'}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
        <XAxis dataKey="period" tick={AXIS} />
        <YAxis domain={[0, 100]} tick={AXIS} unit="%" />
        <Tooltip {...TOOLTIP} formatter={(v, n, p) => [`${v}% (${p.payload.responses} ratings)`, 'Satisfied']} />
        <Line type="monotone" dataKey="satisfaction_pct" stroke={C.teal} strokeWidth={2} dot={{ r: 4, fill: C.teal }} />
      </LineChart>
    </ChartPanel>
  )
}

export function WastageChart({ data }) {
  return (
    <ChartPanel title="Products saved from wastage" subtitle="Units contained, as recorded by admins at resolution"
      empty={!data?.length && 'No contained units recorded yet. Admins enter them when resolving an incident.'}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
        <XAxis dataKey="period" tick={AXIS} />
        <YAxis tick={AXIS} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey="units_contained" name="Units contained" fill={C.teal} radius={[4, 4, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ChartPanel>
  )
}
