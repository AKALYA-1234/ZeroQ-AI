import React, { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  AlertTriangle, Shield, Search, Filter, Download, Info, Eye,
  ChevronDown, ChevronRight, Bell, TrendingUp, Package, MapPin,
  Calendar, FileText, GitBranch, Wrench, RefreshCw, AlertCircle
} from 'lucide-react'
import api from '../../services/api'

const RISK_COLORS = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }
const RISK_BG = { critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700', medium: 'bg-amber-100 text-amber-700', low: 'bg-green-100 text-green-700' }
const MATRIX_COLORS = [
  ['#22c55e','#22c55e','#f59e0b','#f97316','#ef4444'],
  ['#22c55e','#f59e0b','#f59e0b','#f97316','#ef4444'],
  ['#f59e0b','#f59e0b','#f97316','#ef4444','#ef4444'],
  ['#f97316','#f97316','#ef4444','#ef4444','#7f1d1d'],
  ['#ef4444','#ef4444','#ef4444','#7f1d1d','#7f1d1d']
]
const LIKELIHOOD = ['Rare','Unlikely','Possible','Likely','Almost Certain']
const IMPACT = ['Negligible','Minor','Moderate','Major','Catastrophic']

function Badge({ children, className }) { return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${className}`}>{children}</span> }

function getRiskLevel(score) {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

export default function RiskAssessment() {
  const [products, setProducts] = useState([])
  const [batches, setBatches] = useState([])
  const [alerts, setAlerts] = useState([])
  const [kpis, setKpis] = useState({})
  const [matrix, setMatrix] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('products')
  const [selectedProduct, setSelectedProduct] = useState(null)

  useEffect(() => { fetchData() }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [prodRes, batchRes, kpiRes, matrixRes, alertRes] = await Promise.all([
        api.get('/api/admin/risk-assessment'),
        api.get('/api/admin/risk-assessment/batches').catch(() => ({ data: { items: [] } })),
        api.get('/api/admin/risk-assessment/kpis').catch(() => ({ data: {} })),
        api.get('/api/admin/risk-assessment/matrix').catch(() => ({ data: { cells: [] } })),
        api.get('/api/admin/risk-assessment/alerts').catch(() => ({ data: { alerts: [] } }))
      ])
      setProducts(prodRes.data?.product_risks || [])
      setBatches(batchRes.data?.items || [])
      setKpis(kpiRes.data || {})
      setMatrix(matrixRes.data?.cells || [])
      setAlerts(alertRes.data?.alerts || alertRes.data || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto"></div>
    </div>
  )

  const riskDist = [
    { level: 'Critical', count: products.filter(p => getRiskLevel(p.severity_score || 0) === 'critical').length, color: RISK_COLORS.critical },
    { level: 'High', count: products.filter(p => getRiskLevel(p.severity_score || 0) === 'high').length, color: RISK_COLORS.high },
    { level: 'Medium', count: products.filter(p => getRiskLevel(p.severity_score || 0) === 'medium').length, color: RISK_COLORS.medium },
    { level: 'Low', count: products.filter(p => getRiskLevel(p.severity_score || 0) === 'low').length, color: RISK_COLORS.low }
  ]
  const totalProducts = products.length

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Risk Assessment</h1>
          <p className="text-sm text-gray-500 mt-1">Evaluate and monitor risk levels across products, batches and manufacturing processes.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700"><Shield size={14} /> Generate Report</button>
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> Export Risk Data</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Products Assessed</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{kpis.products_assessed || totalProducts}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Batches Assessed</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{kpis.batches_assessed || batches.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-red-500">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Critical Risk</div>
          <div className="text-2xl font-bold text-red-600 mt-1">{kpis.critical || riskDist[0].count}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-orange-500">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">High Risk</div>
          <div className="text-2xl font-bold text-orange-600 mt-1">{kpis.high || riskDist[1].count}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-amber-500">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Medium Risk</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{kpis.medium || riskDist[2].count}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Pending Assessment</div>
          <div className="text-2xl font-bold text-gray-500 mt-1">{kpis.pending || 0}</div>
        </div>
      </div>

      {/* Risk Distribution + Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Risk Distribution</h3>
          <div className="space-y-3">
            {riskDist.map((r, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: r.color }}></span>
                    <span className="text-xs font-medium text-gray-700">{r.level}</span>
                  </div>
                  <span className="text-xs font-semibold text-gray-600">{r.count} products ({totalProducts > 0 ? ((r.count / totalProducts) * 100).toFixed(0) : 0}%)</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-3">
                  <div className="h-full rounded-full transition-all" style={{ width: `${totalProducts > 0 ? (r.count / totalProducts) * 100 : 0}%`, backgroundColor: r.color }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Matrix */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-3">Risk Matrix (5×5)</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="w-20"></th>
                  {IMPACT.map(imp => <th key={imp} className="text-[9px] text-gray-500 font-medium p-1 text-center">{imp}</th>)}
                </tr>
              </thead>
              <tbody>
                {LIKELIHOOD.slice().reverse().map((lik, li) => (
                  <tr key={lik}>
                    <td className="text-[9px] text-gray-500 font-medium pr-2 text-right">{lik}</td>
                    {IMPACT.map((imp, ii) => {
                      const ri = 4 - li
                      const cell = matrix.find(c => c.likelihood === ri && c.impact === ii)
                      return (
                        <td key={imp} className="p-0.5">
                          <div className="w-full aspect-square rounded flex items-center justify-center text-white text-[10px] font-bold cursor-pointer hover:opacity-80 transition-opacity" style={{ backgroundColor: MATRIX_COLORS[ri]?.[ii] || '#d1d5db', minHeight: 32 }}>
                            {cell?.count || 0}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-center mt-2">
              <span className="text-[9px] text-gray-400">← Impact / Severity →</span>
            </div>
          </div>
        </div>
      </div>

      {/* Product Risk Table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-gray-900">Product Risk Ranking</h3>
          <div className="flex gap-1">
            <button onClick={() => setActiveTab('products')} className={`px-3 py-1 rounded-md text-xs font-medium ${activeTab === 'products' ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:bg-gray-100'}`}>Products</button>
            <button onClick={() => setActiveTab('batches')} className={`px-3 py-1 rounded-md text-xs font-medium ${activeTab === 'batches' ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:bg-gray-100'}`}>Batches</button>
          </div>
        </div>

        {activeTab === 'products' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Product</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Code</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Complaints</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Severity Score</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Risk Level</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p, i) => {
                  const risk = getRiskLevel(p.severity_score || 0)
                  return (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer" onClick={() => setSelectedProduct(selectedProduct === i ? null : i)}>
                      <td className="py-2.5 px-3 font-medium text-gray-800">{p.product_name}</td>
                      <td className="py-2.5 px-3 font-mono text-gray-600">{p.product_id}</td>
                      <td className="py-2.5 px-3 text-gray-700">{p.complaint_count}</td>
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-100 rounded-full h-2"><div className="h-full rounded-full" style={{ width: `${Math.min((p.severity_score || 0), 100)}%`, backgroundColor: RISK_COLORS[risk] }}></div></div>
                          <span className="text-gray-700 font-medium">{(p.severity_score || 0).toFixed(1)}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-3"><Badge className={RISK_BG[risk]}>{risk.toUpperCase()}</Badge></td>
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-1">
                          <button className="p-1 text-gray-400 hover:text-teal-600" title="View Details"><Eye size={14} /></button>
                          <button className="p-1 text-gray-400 hover:text-purple-600" title="Investigate"><GitBranch size={14} /></button>
                          <button className="p-1 text-gray-400 hover:text-amber-600" title="Create CAPA"><Wrench size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {products.length === 0 && (
                  <tr><td colSpan={6} className="text-center py-8 text-gray-400">No product risk data available</td></tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Batch ID</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Product</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Facility</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Production Date</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Risk Score</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Risk Level</th>
                </tr>
              </thead>
              <tbody>
                {batches.slice(0, 20).map((b, i) => {
                  const risk = getRiskLevel(b.risk_score || b.severity_score || 0)
                  return (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2.5 px-3 font-mono text-teal-700">{b.batch_id}</td>
                      <td className="py-2.5 px-3 text-gray-700">{b.product_name || 'N/A'}</td>
                      <td className="py-2.5 px-3 text-gray-600">{b.facility_name || 'N/A'}</td>
                      <td className="py-2.5 px-3 text-gray-600">{b.production_date ? new Date(b.production_date).toLocaleDateString() : '—'}</td>
                      <td className="py-2.5 px-3 font-medium">{(b.risk_score || b.severity_score || 0).toFixed(1)}</td>
                      <td className="py-2.5 px-3"><Badge className={RISK_BG[risk]}>{risk.toUpperCase()}</Badge></td>
                    </tr>
                  )
                })}
                {batches.length === 0 && (
                  <tr><td colSpan={6} className="text-center py-8 text-gray-400">No batch risk data available</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Early Warning Alerts */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Bell size={16} className="text-amber-600" />
          <h3 className="text-sm font-bold text-gray-900">Early Warning Alerts</h3>
        </div>
        {Array.isArray(alerts) && alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${alert.severity === 'critical' ? 'bg-red-50 border-red-200' : alert.severity === 'high' ? 'bg-orange-50 border-orange-200' : 'bg-amber-50 border-amber-200'}`}>
                <AlertTriangle size={16} className={alert.severity === 'critical' ? 'text-red-500' : alert.severity === 'high' ? 'text-orange-500' : 'text-amber-500'} />
                <div className="flex-1">
                  <div className="text-xs font-semibold text-gray-800">{alert.title || alert.message}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">{alert.description || alert.details || ''}</div>
                </div>
                <button className="text-xs text-teal-600 hover:text-teal-700 font-medium">View</button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-400">
            <Shield size={24} className="mx-auto mb-2" />
            <p className="text-sm">No active alerts. Risk monitoring is operational.</p>
          </div>
        )}
      </div>

      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-[10px] text-gray-500 flex items-center gap-1.5">
          <Info size={12} className="text-slate-400" />
          Risk scores are calculated using complaint frequency × severity weighting methodology. Pre-dispatch predictions use only features available before dispatch.
        </p>
      </div>
    </div>
  )
}
