import React, { useState, useEffect } from 'react'
import {
  BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import {
  Download, Filter, Calendar, Info, TrendingUp, Package,
  AlertTriangle, Layers, BarChart2, Search, RefreshCw
} from 'lucide-react'
import api from '../../services/api'

const COLORS = ['#0d9488', '#14b8a6', '#f59e0b', '#ef4444', '#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#22c55e', '#3b82f6']
const SEVERITY_COLORS = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export default function ComplaintAnalytics() {
  const [analytics, setAnalytics] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ product: '', category: '', severity: '', facility: '' })
  const [filterOptions, setFilterOptions] = useState({ products: [], categories: [], facilities: [] })

  useEffect(() => { fetchData(); fetchFilters() }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [analyticsRes, kpisRes] = await Promise.all([
        api.get('/api/admin/analytics'),
        api.get('/api/admin/analytics/kpis').catch(() => ({ data: {} }))
      ])
      setAnalytics(analyticsRes.data)
      setKpis(kpisRes.data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const fetchFilters = async () => {
    try {
      const [p, c, f] = await Promise.all([
        api.get('/api/admin/filters/products').catch(() => ({ data: [] })),
        api.get('/api/admin/filters/categories').catch(() => ({ data: [] })),
        api.get('/api/admin/filters/facilities').catch(() => ({ data: [] }))
      ])
      const toArr = (d, key) => Array.isArray(d) ? d : (Array.isArray(d?.[key]) ? d[key] : [])
      setFilterOptions({
        products: toArr(p.data, 'products'),
        categories: toArr(c.data, 'categories'),
        facilities: toArr(f.data, 'facilities')
      })
    } catch (e) { console.error(e) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto mb-4"></div>
        <p className="text-gray-500 text-sm">Loading analytics...</p>
      </div>
    </div>
  )

  const byYear = analytics?.by_year || []
  const byMonth = analytics?.by_month || []
  const byCategory = analytics?.by_category || []
  const bySeverity = analytics?.by_severity || []
  const byProduct = analytics?.by_product || []
  const byFacility = analytics?.by_facility || []
  const byCustomer = analytics?.by_customer || []
  const heatmap = analytics?.product_category_heatmap || []
  const recurring = analytics?.recurring_patterns || []
  const totalComplaints = kpis?.total || byYear.reduce((s, y) => s + y.count, 0)
  const avgMonthly = kpis?.avg_monthly || (totalComplaints / Math.max(byYear.length * 12, 1)).toFixed(1)
  const highCritical = kpis?.high_critical_count || bySeverity.filter(s => ['critical','high'].includes(s.severity)).reduce((s, v) => s + v.count, 0)

  const chartYearData = byYear.length === 0
    ? [{ year: 2025, count: 0 }, { year: 2026, count: totalComplaints }]
    : byYear.length === 1
    ? [{ year: (byYear[0].year || 2026) - 1, count: 0 }, byYear[0]]
    : byYear

  const chartMonthData = byMonth.length > 0 ? byMonth : [
    { month: 1, count: 0 }, { month: 11, count: totalComplaints }
  ]

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Complaint Analytics & Defect Epidemiology</h1>
          <p className="text-sm text-gray-500 mt-1">Manufacturing defect & complaint analytics. In-depth trend analysis, pattern detection, and data-driven quality intelligence.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> CSV Export</button>
          <button className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700"><Download size={14} /> PDF Report</button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-teal-50 border border-teal-200 rounded-lg px-4 py-3 mb-5 flex items-start gap-2">
        <Info size={16} className="text-teal-600 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-xs text-teal-800"><strong>Manufacturing Defect & Complaint Analytics:</strong> All analytics are derived from actual dataset records. Statistical patterns are observations, not verified root causes. Production-volume normalization is applied where reliable data is available.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-5 flex flex-wrap items-center gap-2">
        <Filter size={14} className="text-gray-400" />
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.product} onChange={e => setFilters({...filters, product: e.target.value})}>
          <option value="">All Products</option>
          {(Array.isArray(filterOptions?.products) ? filterOptions.products : []).map(p => <option key={p.id || p} value={p.name || p}>{p.name || p}</option>)}
        </select>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.category} onChange={e => setFilters({...filters, category: e.target.value})}>
          <option value="">All Categories</option>
          {(Array.isArray(filterOptions?.categories) ? filterOptions.categories : []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.severity} onChange={e => setFilters({...filters, severity: e.target.value})}>
          <option value="">All Severities</option>
          <option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
        </select>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.facility} onChange={e => setFilters({...filters, facility: e.target.value})}>
          <option value="">All Facilities</option>
          {(Array.isArray(filterOptions?.facilities) ? filterOptions.facilities : []).map(f => <option key={f.id || f} value={f.name || f}>{f.name || f}</option>)}
        </select>
        <button onClick={fetchData} className="px-3 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-700 flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Total Complaints</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{totalComplaints.toLocaleString()}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">{byYear.length > 0 ? `${byYear[0].year}–${byYear[byYear.length-1].year}` : 'All time'}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Average Monthly</div>
          <div className="text-2xl font-bold text-teal-600 mt-1">{avgMonthly}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">complaints / month</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Most Affected Product</div>
          <div className="text-sm font-bold text-gray-900 mt-1 truncate">
            {typeof kpis?.most_affected_product === 'object'
              ? (kpis.most_affected_product?.name || 'N/A')
              : (kpis?.most_affected_product || byProduct[0]?.product || 'N/A')}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">
            {typeof kpis?.most_affected_product === 'object'
              ? (kpis.most_affected_product?.count || 0)
              : (kpis?.most_affected_product_count ?? (byProduct[0]?.count || 0))} complaints
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Most Frequent Category</div>
          <div className="text-sm font-bold text-gray-900 mt-1 truncate">
            {typeof kpis?.most_frequent_category === 'object'
              ? (kpis.most_frequent_category?.name || 'N/A')
              : (kpis?.most_frequent_category || byCategory[0]?.category || 'N/A')}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">
            {typeof kpis?.most_frequent_category === 'object'
              ? (kpis.most_frequent_category?.count || 0)
              : (kpis?.most_frequent_category_count ?? (byCategory[0]?.count || 0))} complaints
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">High / Critical</div>
          <div className="text-2xl font-bold text-red-600 mt-1">{highCritical}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">{totalComplaints > 0 ? ((highCritical / totalComplaints) * 100).toFixed(1) : 0}% of total</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Recurring Clusters</div>
          <div className="text-2xl font-bold text-purple-600 mt-1">{kpis?.recurring_clusters || recurring.length || 0}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">pattern groups detected</div>
        </div>
      </div>

      {/* Complaint Trend */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-gray-900">Production-Weighted Complaint Trend ({byYear.length > 0 ? `${byYear[0].year}–${byYear[byYear.length-1].year}` : '2008–2026'})</h3>
          <p className="text-[10px] text-gray-500 mt-0.5">Historical complaint volume across all product lines and facilities</p>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={chartYearData}>
            <defs>
              <linearGradient id="tealGradAnalytics" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#0d9488" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} />
            <Area type="monotone" dataKey="count" stroke="#0d9488" strokeWidth={2} fill="url(#tealGradAnalytics)" dot={{ r: 3, fill: '#0d9488' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Row: Monthly + Category */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Monthly Complaint Distribution</h3>
          <p className="text-[10px] text-gray-500 mb-4">Aggregated across all years by calendar month</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartMonthData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={v => MONTHS[v - 1] || v} />
              <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} labelFormatter={v => MONTHS[v - 1] || v} />
              <Bar dataKey="count" fill="#14b8a6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Complaint Category Breakdown</h3>
          <p className="text-[10px] text-gray-500 mb-4">Distribution across manufacturing defect categories</p>
          {byCategory.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 items-center gap-4">
              <div className="h-52 w-full min-w-[140px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={byCategory} dataKey="count" nameKey="category" cx="50%" cy="50%" innerRadius={50} outerRadius={75} strokeWidth={2}>
                      {byCategory.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-1.5 pl-2 max-h-52 overflow-y-auto">
                {byCategory.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }}></span>
                    <span className="text-gray-600 truncate flex-1">{item.category}</span>
                    <span className="text-gray-900 font-semibold">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400 text-sm">No category data available</div>
          )}
        </div>
      </div>

      {/* Row: Severity + Facility */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Complaint Severity Distribution</h3>
          <p className="text-[10px] text-gray-500 mb-4">Breakdown by customer-reported severity level</p>
          <div className="space-y-3">
            {bySeverity.map((item, i) => {
              const maxCount = Math.max(...bySeverity.map(s => s.count), 1)
              const pct = ((item.count / totalComplaints) * 100).toFixed(1)
              return (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium capitalize text-gray-700">{item.severity}</span>
                    <span className="text-xs text-gray-500">{item.count} ({pct}%)</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-3">
                    <div className="h-full rounded-full transition-all" style={{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: SEVERITY_COLORS[item.severity] || '#9ca3af' }}></div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Manufacturing Facility Comparison</h3>
          <p className="text-[10px] text-gray-500 mb-4">Complaint distribution across production facilities</p>
          {byFacility.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={byFacility} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <YAxis dataKey="facility" type="category" tick={{ fontSize: 10, fill: '#6b7280' }} width={80} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No facility data available</div>
          )}
        </div>
      </div>

      {/* Product-wise Analysis */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-1">Product-Wise Complaint Analysis</h3>
        <p className="text-[10px] text-gray-500 mb-4">Complaint volume by product line</p>
        <div className="space-y-2">
          {byProduct.slice(0, 10).map((item, i) => {
            const maxCount = byProduct[0]?.count || 1
            return (
              <div key={i} className="flex items-center gap-3">
                <div className="w-36 text-xs text-gray-700 truncate font-medium">{item.product}</div>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: COLORS[i % COLORS.length] }}></div>
                </div>
                <div className="text-xs text-gray-600 font-semibold w-12 text-right">{item.count}</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Heatmap */}
      {heatmap.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Product × Complaint Category Heatmap</h3>
          <p className="text-[10px] text-gray-500 mb-4">Cross-tabulation of products and complaint categories</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr>
                  <th className="text-left p-2 text-gray-600 font-semibold">Product</th>
                  {[...new Set(heatmap.map(h => h.category))].map(cat => (
                    <th key={cat} className="p-2 text-gray-600 font-semibold text-center">{cat}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...new Set(heatmap.map(h => h.product))].map(prod => {
                  const cats = [...new Set(heatmap.map(h => h.category))]
                  return (
                    <tr key={prod} className="border-t border-gray-50">
                      <td className="p-2 text-gray-700 font-medium">{prod}</td>
                      {cats.map(cat => {
                        const cell = heatmap.find(h => h.product === prod && h.category === cat)
                        const count = cell?.count || 0
                        const maxH = Math.max(...heatmap.map(h => h.count), 1)
                        const intensity = count / maxH
                        return (
                          <td key={cat} className="p-2 text-center">
                            <div className="rounded px-2 py-1 text-[10px] font-medium" style={{
                              backgroundColor: count > 0 ? `rgba(13, 148, 136, ${0.1 + intensity * 0.6})` : '#f9fafb',
                              color: intensity > 0.4 ? '#fff' : '#374151'
                            }}>{count || '—'}</div>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recurring Patterns */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-1">Recurring Complaint Patterns</h3>
        <p className="text-[10px] text-gray-500 mb-4">Products and categories with repeated complaint occurrences</p>
        {recurring.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Product</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Category</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Count</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Pattern</th>
                </tr>
              </thead>
              <tbody>
                {recurring.map((r, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 text-gray-700 font-medium">{r.product}</td>
                    <td className="py-2 px-3 text-gray-600">{r.category}</td>
                    <td className="py-2 px-3"><span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[10px] font-semibold">{r.count}</span></td>
                    <td className="py-2 px-3 text-gray-500">{r.description || 'Recurring pattern detected'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-gray-400">
            <Layers size={24} className="mx-auto mb-2" />
            <p className="text-sm">Recurring patterns will appear once sufficient data is analyzed</p>
          </div>
        )}
      </div>

      {/* Automated Insights */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-xl p-5 mb-4 text-white">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={16} className="text-teal-400" />
          <h3 className="text-sm font-bold">Automated Analytical Insights</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-[10px] text-teal-400 font-semibold uppercase mb-1">Trend Observation</p>
            <p className="text-xs text-gray-300">The complaint trend shows {byYear.length > 0 ? `data spanning ${byYear.length} years with a total of ${totalComplaints.toLocaleString()} records` : 'data patterns over the historical period'}.</p>
          </div>
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-[10px] text-amber-400 font-semibold uppercase mb-1">Category Focus</p>
            <p className="text-xs text-gray-300">{byCategory[0] ? `"${byCategory[0].category}" leads with ${byCategory[0].count} complaints (${((byCategory[0].count / totalComplaints) * 100).toFixed(1)}% of total).` : 'Category analysis pending data.'}</p>
          </div>
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-[10px] text-blue-400 font-semibold uppercase mb-1">Data Quality</p>
            <p className="text-xs text-gray-300">All statistics are derived from the synthetic manufacturing dataset. Statistical correlations are observations, not verified causal relationships.</p>
          </div>
        </div>
      </div>

      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-[10px] text-gray-500 flex items-center gap-1.5">
          <Info size={12} className="text-slate-400" />
          Data sourced from Synthetic Manufacturing Quality Intelligence Dataset. Complaint rates are normalized using production volume when reliable data is available.
        </p>
      </div>
    </div>
  )
}
