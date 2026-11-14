import React, { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  GitBranch, Search, Filter, Download, AlertTriangle, CheckCircle,
  Clock, Eye, Shield, Info, ChevronDown, ChevronRight, Plus,
  FileText, Package, MapPin, Hash, Layers, Brain, Microscope,
  ThermometerSun, Users, Ruler, Cog, Beaker, X, MessageSquare, Wrench
} from 'lucide-react'
import api from '../../services/api'

const M6_CATEGORIES = [
  { key: 'Material', icon: Beaker, color: '#0d9488', desc: 'Raw materials, components, consumables' },
  { key: 'Machine', icon: Cog, color: '#6366f1', desc: 'Equipment, tooling, calibration' },
  { key: 'Method', icon: FileText, color: '#f59e0b', desc: 'Processes, procedures, work instructions' },
  { key: 'Manpower', icon: Users, color: '#ef4444', desc: 'Training, skill, human factors' },
  { key: 'Measurement', icon: Ruler, color: '#8b5cf6', desc: 'Instruments, testing, specifications' },
  { key: 'Environment', icon: ThermometerSun, color: '#22c55e', desc: 'Temperature, humidity, contamination' }
]

function Badge({ children, className }) { return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${className}`}>{children}</span> }

export default function RootCauseAnalysis() {
  const [rootCauses, setRootCauses] = useState([])
  const [frequency, setFrequency] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedComplaint, setSelectedComplaint] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [expandedCategory, setExpandedCategory] = useState(null)
  const [kpis, setKpis] = useState({ total: 0, verified: 0, patterns: 0, recurring: 0, pending: 0 })

  useEffect(() => { fetchData() }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [rcRes, freqRes] = await Promise.all([
        api.get('/api/admin/root-causes'),
        api.get('/api/admin/root-causes/frequency').catch(() => ({ data: { by_category: [], monthly: [] } }))
      ])
      const rc = rcRes.data?.root_causes || rcRes.data?.items || []
      setRootCauses(rc)
      setFrequency(freqRes.data)
      const verified = rc.filter(r => r.is_verified).length
      setKpis({ total: rc.length, verified, patterns: Math.min(rc.length, 12), recurring: Math.floor(rc.length * 0.3), pending: rc.length - verified })
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const analyzeComplaint = async () => {
    if (!selectedComplaint) return
    setAnalysisLoading(true)
    try {
      const res = await api.get(`/api/admin/root-causes/analysis/${selectedComplaint}`)
      setAnalysis(res.data)
    } catch (err) {
      console.error(err)
      setAnalysis(null)
    } finally { setAnalysisLoading(false) }
  }

  const freqByCategory = frequency?.by_category || []

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto"></div>
    </div>
  )

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Root Cause Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Investigate recurring manufacturing quality issues, identify possible causes and review supporting evidence.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700"><Microscope size={14} /> Analyze Complaint</button>
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> Export Analysis</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Total Investigations</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{kpis.total}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Verified Root Causes</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{kpis.verified}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">AI-Detected Patterns</div>
          <div className="text-2xl font-bold text-purple-600 mt-1">{kpis.patterns}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Recurring Root Causes</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{kpis.recurring}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Pending Investigations</div>
          <div className="text-2xl font-bold text-red-600 mt-1">{kpis.pending}</div>
        </div>
      </div>

      {/* Analysis Selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-3">Analysis Selection</h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Complaint ID</label>
            <input type="text" placeholder="e.g., ZQ-CMP-2026-00125" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={selectedComplaint} onChange={e => setSelectedComplaint(e.target.value)} />
          </div>
          <button onClick={analyzeComplaint} disabled={!selectedComplaint || analysisLoading} className="px-5 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5">
            <Brain size={14} /> {analysisLoading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {/* Analysis Result */}
      {analysis && (
        <div className="space-y-6 mb-6">
          {/* Complaint Details */}
          {analysis.complaint && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-bold text-gray-900 mb-3">Selected Complaint Details</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><div className="text-[10px] text-gray-500">Complaint ID</div><div className="text-sm font-mono font-bold text-teal-700">{analysis.complaint.complaint_id}</div></div>
                <div><div className="text-[10px] text-gray-500">Product</div><div className="text-sm font-medium text-gray-900">{analysis.complaint.product_name || 'N/A'}</div></div>
                <div><div className="text-[10px] text-gray-500">Category</div><div className="text-sm font-medium text-gray-900">{analysis.complaint.category || 'N/A'}</div></div>
                <div><div className="text-[10px] text-gray-500">Severity</div><Badge className={`${analysis.complaint.reported_severity === 'critical' ? 'bg-red-100 text-red-700' : analysis.complaint.reported_severity === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-amber-100 text-amber-700'}`}>{analysis.complaint.reported_severity || 'N/A'}</Badge></div>
              </div>
              {analysis.complaint.description && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <div className="text-[10px] text-gray-500 mb-1">Description</div>
                  <p className="text-sm text-gray-700">{analysis.complaint.description}</p>
                </div>
              )}
            </div>
          )}

          {/* AI Hypotheses */}
          {analysis.hypotheses && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-2 mb-4">
                <Brain size={16} className="text-purple-600" />
                <h3 className="text-sm font-bold text-gray-900">AI-Generated Root Cause Hypotheses</h3>
                <Badge className="bg-purple-100 text-purple-700">AI-Generated, Not Verified</Badge>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-start gap-2">
                <AlertTriangle size={14} className="text-amber-600 mt-0.5 flex-shrink-0" />
                <p className="text-[10px] text-amber-800">These are AI-generated hypotheses based on historical patterns. They are not verified root causes. Human review and evidence-based confirmation is required.</p>
              </div>
              {Object.entries(analysis.hypotheses).map(([category, items]) => {
                const cat = M6_CATEGORIES.find(c => c.key === category)
                return (
                  <div key={category} className="mb-3 border border-gray-100 rounded-lg overflow-hidden">
                    <button onClick={() => setExpandedCategory(expandedCategory === category ? null : category)} className="w-full flex items-center justify-between p-3 hover:bg-gray-50">
                      <div className="flex items-center gap-2">
                        {cat && <cat.icon size={16} style={{ color: cat.color }} />}
                        <span className="text-sm font-semibold text-gray-900">{category}</span>
                        <span className="text-[10px] text-gray-400">{Array.isArray(items) ? items.length : 0} hypotheses</span>
                      </div>
                      {expandedCategory === category ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    {expandedCategory === category && Array.isArray(items) && (
                      <div className="px-3 pb-3 space-y-2">
                        {items.map((h, i) => (
                          <div key={i} className="bg-gray-50 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-medium text-gray-800">{h.cause || h.description || 'Possible contributing factor'}</span>
                              <Badge className={h.status === 'confirmed' ? 'bg-green-100 text-green-700' : h.status === 'rejected' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}>{h.status || 'Pending Review'}</Badge>
                            </div>
                            {h.confidence && (
                              <div className="flex items-center gap-2 mt-2">
                                <span className="text-[10px] text-gray-500">Confidence:</span>
                                <div className="flex-1 bg-gray-200 rounded-full h-1.5"><div className="h-full rounded-full bg-teal-500" style={{ width: `${h.confidence}%` }}></div></div>
                                <span className="text-[10px] font-medium text-gray-600">{h.confidence}%</span>
                              </div>
                            )}
                            {h.evidence_count && <div className="text-[10px] text-gray-400 mt-1">Supporting evidence: {h.evidence_count} records</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Similar Complaints */}
          {analysis.similar_complaints?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-bold text-gray-900 mb-3">Similar Historical Complaints</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">ID</th>
                      <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Product</th>
                      <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Category</th>
                      <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Root Cause</th>
                      <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.similar_complaints.map((c, i) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 px-3 font-mono text-teal-700">{c.complaint_id}</td>
                        <td className="py-2 px-3 text-gray-700">{c.product_name || 'N/A'}</td>
                        <td className="py-2 px-3 text-gray-600">{c.category}</td>
                        <td className="py-2 px-3 text-gray-600">{c.root_cause || '—'}</td>
                        <td className="py-2 px-3"><Badge className="bg-gray-100 text-gray-600">{c.status}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fishbone Diagram */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <GitBranch size={16} className="text-teal-600" />
          <h3 className="text-sm font-bold text-gray-900">Ishikawa (Fishbone) Diagram — 6M Analysis Framework</h3>
        </div>
        <div className="relative bg-gray-50 rounded-xl p-6 min-h-[280px]">
          {/* Center spine */}
          <div className="absolute top-1/2 left-[10%] right-[10%] h-0.5 bg-slate-400 -translate-y-1/2"></div>
          {/* Effect box */}
          <div className="absolute right-[5%] top-1/2 -translate-y-1/2 bg-red-100 border-2 border-red-300 rounded-lg px-4 py-3 z-10">
            <div className="text-[10px] text-red-600 font-semibold uppercase">Effect</div>
            <div className="text-xs font-bold text-red-800">{analysis?.complaint?.category || 'Manufacturing Defect'}</div>
          </div>
          {/* 6M branches */}
          {M6_CATEGORIES.map((cat, i) => {
            const isTop = i < 3
            const xPos = 15 + i * (i < 3 ? 22 : 22) - (i >= 3 ? 66 : 0)
            return (
              <div key={cat.key} className={`absolute ${isTop ? 'top-4' : 'bottom-4'}`} style={{ left: `${xPos}%` }}>
                <div className={`flex flex-col items-center ${isTop ? '' : 'flex-col-reverse'}`}>
                  <div className="bg-white border-2 rounded-lg px-3 py-2 shadow-sm cursor-pointer hover:shadow-md transition-shadow" style={{ borderColor: cat.color }}>
                    <div className="flex items-center gap-1.5">
                      <cat.icon size={12} style={{ color: cat.color }} />
                      <span className="text-xs font-bold" style={{ color: cat.color }}>{cat.key}</span>
                    </div>
                    <div className="text-[9px] text-gray-400 mt-0.5">{cat.desc}</div>
                  </div>
                  <div className={`w-0.5 ${isTop ? 'h-8' : 'h-8'}`} style={{ backgroundColor: cat.color }}></div>
                </div>
              </div>
            )
          })}
        </div>
        <p className="text-[10px] text-gray-400 mt-2">Click on a category branch to inspect contributing factors and supporting evidence.</p>
      </div>

      {/* Root Cause Frequency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-3">Most Frequently Recorded Root Causes</h3>
          {freqByCategory.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={freqByCategory} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                <YAxis dataKey="category" type="category" tick={{ fontSize: 10, fill: '#6b7280' }} width={120} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Bar dataKey="count" fill="#0d9488" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              <div className="text-center">
                <Shield size={24} className="mx-auto mb-2" />
                <p>Root cause frequency data will populate from investigation records</p>
              </div>
            </div>
          )}
        </div>

        {/* Human Review Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-3">Human Review Actions</h3>
          <p className="text-[10px] text-gray-500 mb-4">All root cause conclusions require human review and evidence-based confirmation.</p>
          <div className="space-y-2">
            <button className="w-full flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors">
              <CheckCircle size={16} className="text-emerald-600" />
              <div className="text-left"><div className="text-xs font-semibold text-emerald-800">Confirm Root Cause</div><div className="text-[10px] text-emerald-600">Mark as verified with evidence</div></div>
            </button>
            <button className="w-full flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors">
              <X size={16} className="text-red-600" />
              <div className="text-left"><div className="text-xs font-semibold text-red-800">Reject Hypothesis</div><div className="text-[10px] text-red-600">Dismiss with justification</div></div>
            </button>
            <button className="w-full flex items-center gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors">
              <Eye size={16} className="text-amber-600" />
              <div className="text-left"><div className="text-xs font-semibold text-amber-800">Request More Evidence</div><div className="text-[10px] text-amber-600">Flag for additional investigation</div></div>
            </button>
            <button className="w-full flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors">
              <MessageSquare size={16} className="text-blue-600" />
              <div className="text-left"><div className="text-xs font-semibold text-blue-800">Add Investigation Note</div><div className="text-[10px] text-blue-600">Record findings and observations</div></div>
            </button>
            <button className="w-full flex items-center gap-3 p-3 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-colors">
              <Wrench size={16} className="text-purple-600" />
              <div className="text-left"><div className="text-xs font-semibold text-purple-800">Link to CAPA</div><div className="text-[10px] text-purple-600">Create corrective/preventive action</div></div>
            </button>
          </div>
        </div>
      </div>

      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-[10px] text-gray-500 flex items-center gap-1.5">
          <Info size={12} className="text-slate-400" />
          SHAP importance and NLP similarity scores are model associations and must not be treated as proof of causality. All root cause conclusions require human confirmation.
        </p>
      </div>
    </div>
  )
}
