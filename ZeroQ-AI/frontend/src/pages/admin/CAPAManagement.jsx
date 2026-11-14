import React, { useState, useEffect } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  Wrench, Plus, Download, Search, Filter, CheckCircle, Clock,
  AlertTriangle, X, Eye, ChevronRight, ChevronLeft, Edit,
  User, Calendar, Package, MapPin, FileText, Shield, Info,
  ArrowRight, MessageSquare, Upload, RefreshCw, AlertCircle
} from 'lucide-react'
import api from '../../services/api'

const COLORS = ['#0d9488', '#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6', '#ec4899']
const PRIORITY_BG = { critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700', medium: 'bg-amber-100 text-amber-700', low: 'bg-green-100 text-green-700' }
const STATUS_BG = { pending: 'bg-gray-100 text-gray-600', in_progress: 'bg-blue-100 text-blue-700', completed: 'bg-green-100 text-green-700', overdue: 'bg-red-100 text-red-700', verified_effective: 'bg-emerald-100 text-emerald-700', ineffective: 'bg-red-100 text-red-700' }
const TYPE_BG = { corrective: 'bg-blue-100 text-blue-700', preventive: 'bg-purple-100 text-purple-700' }

function Badge({ children, className }) { return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${className}`}>{children}</span> }

const TIMELINE_STAGES = ['CAPA Created', 'Action Assigned', 'Action Started', 'Action Completed', 'Effectiveness Verification', 'Final Closure']

export default function CAPAManagement() {
  const [capaList, setCAPAList] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [overdue, setOverdue] = useState([])
  const [effectiveness, setEffectiveness] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [selectedCAPA, setSelectedCAPA] = useState(null)
  const [detailView, setDetailView] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [activeDetailTab, setActiveDetailTab] = useState('details')
  const [filters, setFilters] = useState({ search: '', status: '', action_type: '', priority: '' })
  const [createForm, setCreateForm] = useState({ title: '', description: '', action_type: 'corrective', priority: 'medium', assigned_to: '', complaint_id: '' })

  useEffect(() => { fetchData() }, [page, filters])

  const fetchData = async () => {
    setLoading(true)
    try {
      const params = { page, per_page: 15 }
      if (filters.status) params.status = filters.status
      if (filters.action_type) params.action_type = filters.action_type
      if (filters.priority) params.priority = filters.priority

      const [listRes, analyticsRes, overdueRes, effRes] = await Promise.all([
        api.get('/api/admin/capa', { params }),
        api.get('/api/admin/capa/analytics').catch(() => ({ data: {} })),
        api.get('/api/admin/capa/overdue').catch(() => ({ data: { items: [] } })),
        api.get('/api/admin/capa/effectiveness').catch(() => ({ data: { items: [] } }))
      ])
      setCAPAList(listRes.data?.items || [])
      setTotal(listRes.data?.total || 0)
      setPages(Math.ceil((listRes.data?.total || 0) / 15))
      setAnalytics(analyticsRes.data)
      setOverdue(overdueRes.data?.items || overdueRes.data || [])
      setEffectiveness(effRes.data?.items || effRes.data || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const fetchDetail = async (capaId) => {
    try {
      const res = await api.get(`/api/admin/capa/${capaId}`)
      setSelectedCAPA(res.data)
      setDetailView(true)
    } catch (err) {
      console.error(err)
    }
  }

  const createCAPA = async () => {
    try {
      await api.post('/api/admin/capa', createForm)
      setShowCreateForm(false)
      setCreateForm({ title: '', description: '', action_type: 'corrective', priority: 'medium', assigned_to: '', complaint_id: '' })
      fetchData()
    } catch (err) { console.error(err) }
  }

  const kpiData = {
    total: total,
    pending: capaList.filter(c => c.status === 'pending').length,
    in_progress: capaList.filter(c => c.status === 'in_progress').length,
    completed: capaList.filter(c => c.status === 'completed').length,
    overdue: Array.isArray(overdue) ? overdue.length : 0,
    verified: capaList.filter(c => c.effectiveness_status === 'verified_effective').length
  }

  const statusDist = analytics?.by_status || []
  const typeDist = analytics?.by_type || []
  const monthlyTrend = analytics?.monthly_trend || []
  const effDist = analytics?.by_effectiveness || []

  const getTimelineStep = (status) => {
    const map = { pending: 0, assigned: 1, in_progress: 2, completed: 3, verification_pending: 4, verified_effective: 5, ineffective: 5, closed: 5 }
    return map[status] || 0
  }

  if (loading && capaList.length === 0) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto"></div>
    </div>
  )

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">CAPA Management</h1>
          <p className="text-sm text-gray-500 mt-1">Track and manage Corrective and Preventive Actions to drive continuous improvement.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button onClick={() => setShowCreateForm(true)} className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700"><Plus size={14} /> Create CAPA</button>
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> Export Report</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Total CAPA Records</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{kpiData.total}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-amber-400">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Pending Actions</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{kpiData.pending}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-blue-400">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">In Progress</div>
          <div className="text-2xl font-bold text-blue-600 mt-1">{kpiData.in_progress}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-green-400">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Completed</div>
          <div className="text-2xl font-bold text-green-600 mt-1">{kpiData.completed}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-red-400">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Overdue</div>
          <div className="text-2xl font-bold text-red-600 mt-1">{kpiData.overdue}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 border-l-4 border-l-emerald-400">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Effectiveness Verified</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{kpiData.verified}</div>
        </div>
      </div>

      {/* Create CAPA Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">Create New CAPA</h3>
              <button onClick={() => setShowCreateForm(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">CAPA Title *</label>
                <input type="text" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={createForm.title} onChange={e => setCreateForm({...createForm, title: e.target.value})} placeholder="Enter CAPA title" />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Description</label>
                <textarea className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none" rows={3} value={createForm.description} onChange={e => setCreateForm({...createForm, description: e.target.value})} placeholder="Describe the corrective/preventive action" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Action Type</label>
                  <select className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" value={createForm.action_type} onChange={e => setCreateForm({...createForm, action_type: e.target.value})}>
                    <option value="corrective">Corrective Action</option>
                    <option value="preventive">Preventive Action</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Priority</label>
                  <select className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" value={createForm.priority} onChange={e => setCreateForm({...createForm, priority: e.target.value})}>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Assigned Owner</label>
                  <input type="text" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={createForm.assigned_to} onChange={e => setCreateForm({...createForm, assigned_to: e.target.value})} placeholder="e.g., Dr. A. Thomas" />
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Related Complaint ID</label>
                  <input type="text" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={createForm.complaint_id} onChange={e => setCreateForm({...createForm, complaint_id: e.target.value})} placeholder="e.g., ZQ-CMP-2026-00125" />
                </div>
              </div>
            </div>
            <div className="p-5 border-t border-gray-100 flex items-center justify-end gap-2">
              <button onClick={() => setShowCreateForm(false)} className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">Cancel</button>
              <button className="px-4 py-2 bg-gray-100 rounded-lg text-sm text-gray-700 hover:bg-gray-200">Save Draft</button>
              <button onClick={createCAPA} disabled={!createForm.title} className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50">Create CAPA</button>
            </div>
          </div>
        </div>
      )}

      {/* CAPA Detail Drawer */}
      {detailView && selectedCAPA && (
        <div className="fixed inset-0 bg-black/50 z-50 flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full overflow-y-auto">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between sticky top-0 bg-white z-10">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold font-mono text-gray-900">{selectedCAPA.capa_id}</span>
                  <Badge className={STATUS_BG[selectedCAPA.status] || 'bg-gray-100 text-gray-600'}>{selectedCAPA.status?.replace(/_/g, ' ')}</Badge>
                  <Badge className={PRIORITY_BG[selectedCAPA.priority] || 'bg-gray-100 text-gray-600'}>{selectedCAPA.priority}</Badge>
                </div>
              </div>
              <button onClick={() => setDetailView(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>

            {/* Timeline */}
            <div className="px-5 py-4 border-b border-gray-100">
              <h4 className="text-xs font-bold text-gray-900 uppercase mb-3">CAPA Timeline</h4>
              <div className="flex items-center gap-1">
                {TIMELINE_STAGES.map((stage, i) => {
                  const currentStep = getTimelineStep(selectedCAPA.status)
                  const isComplete = i <= currentStep
                  const isCurrent = i === currentStep
                  return (
                    <React.Fragment key={i}>
                      <div className="flex flex-col items-center flex-1">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold ${isComplete ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-500'} ${isCurrent ? 'ring-2 ring-teal-300' : ''}`}>{i + 1}</div>
                        <span className={`text-[8px] mt-1 text-center ${isComplete ? 'text-teal-700 font-medium' : 'text-gray-400'}`}>{stage}</span>
                      </div>
                      {i < TIMELINE_STAGES.length - 1 && <div className={`h-0.5 flex-1 ${i < currentStep ? 'bg-teal-500' : 'bg-gray-200'}`}></div>}
                    </React.Fragment>
                  )
                })}
              </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-100 px-5">
              <div className="flex gap-0">
                {['details', 'timeline', 'effectiveness'].map(tab => (
                  <button key={tab} onClick={() => setActiveDetailTab(tab)} className={`px-3 py-2.5 text-xs font-medium border-b-2 capitalize ${activeDetailTab === tab ? 'border-teal-600 text-teal-700' : 'border-transparent text-gray-500'}`}>{tab}</button>
                ))}
              </div>
            </div>

            <div className="p-5">
              {activeDetailTab === 'details' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div><div className="text-[10px] text-gray-500">Title</div><div className="text-sm font-medium text-gray-900">{selectedCAPA.title}</div></div>
                    <div><div className="text-[10px] text-gray-500">Action Type</div><Badge className={TYPE_BG[selectedCAPA.action_type] || 'bg-gray-100'}>{selectedCAPA.action_type}</Badge></div>
                    <div><div className="text-[10px] text-gray-500">Priority</div><Badge className={PRIORITY_BG[selectedCAPA.priority] || 'bg-gray-100'}>{selectedCAPA.priority}</Badge></div>
                    <div><div className="text-[10px] text-gray-500">Assigned To</div><div className="text-sm text-gray-800">{selectedCAPA.assigned_to || 'Unassigned'}</div></div>
                    <div><div className="text-[10px] text-gray-500">Deadline</div><div className="text-sm text-gray-800">{selectedCAPA.deadline ? new Date(selectedCAPA.deadline).toLocaleDateString() : 'Not set'}</div></div>
                    <div><div className="text-[10px] text-gray-500">Created</div><div className="text-sm text-gray-800">{selectedCAPA.created_at ? new Date(selectedCAPA.created_at).toLocaleDateString() : '—'}</div></div>
                  </div>
                  {selectedCAPA.description && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="text-[10px] text-gray-500 mb-1">Description</div>
                      <p className="text-sm text-gray-700">{selectedCAPA.description}</p>
                    </div>
                  )}
                  <div className="flex gap-2 pt-3">
                    <button className="px-3 py-2 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-700 flex items-center gap-1"><Edit size={12} /> Update Status</button>
                    <button className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-1"><MessageSquare size={12} /> Add Note</button>
                    <button className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-1"><Upload size={12} /> Upload Evidence</button>
                  </div>
                </div>
              )}
              {activeDetailTab === 'effectiveness' && (
                <div className="space-y-4">
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                    <Info size={14} className="text-amber-600 mt-0.5" />
                    <p className="text-[10px] text-amber-800">A completed action is not automatically effective. Evidence and follow-up verification are required.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-[10px] text-gray-500">Effectiveness Status</div>
                      <Badge className={`mt-1 ${selectedCAPA.effectiveness_status === 'verified_effective' ? 'bg-emerald-100 text-emerald-700' : selectedCAPA.effectiveness_status === 'ineffective' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{selectedCAPA.effectiveness_status?.replace(/_/g, ' ') || 'Pending Verification'}</Badge>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-[10px] text-gray-500">Verified At</div>
                      <div className="text-xs font-medium text-gray-800 mt-1">{selectedCAPA.verified_at ? new Date(selectedCAPA.verified_at).toLocaleDateString() : 'Not yet verified'}</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="px-3 py-2 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 flex items-center gap-1"><CheckCircle size={12} /> Mark Effective</button>
                    <button className="px-3 py-2 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 flex items-center gap-1"><X size={12} /> Mark Ineffective</button>
                    <button className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-1"><RefreshCw size={12} /> Start Review</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 flex flex-wrap items-center gap-2">
        <div className="flex items-center bg-gray-100 rounded-lg px-3 py-1.5 min-w-[200px]">
          <Search size={14} className="text-gray-400 mr-2" />
          <input placeholder="Search CAPA ID, title..." className="bg-transparent text-sm focus:outline-none w-full" value={filters.search} onChange={e => setFilters({...filters, search: e.target.value})} />
        </div>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.status} onChange={e => setFilters({...filters, status: e.target.value})}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option><option value="in_progress">In Progress</option><option value="completed">Completed</option><option value="overdue">Overdue</option>
        </select>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.action_type} onChange={e => setFilters({...filters, action_type: e.target.value})}>
          <option value="">All Types</option>
          <option value="corrective">Corrective</option><option value="preventive">Preventive</option>
        </select>
        <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.priority} onChange={e => setFilters({...filters, priority: e.target.value})}>
          <option value="">All Priorities</option>
          <option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
        </select>
        <button onClick={fetchData} className="px-3 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-700 flex items-center gap-1"><Filter size={12} /> Apply</button>
      </div>

      {/* CAPA Table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">CAPA ID</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Title</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Type</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Priority</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Assigned To</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Deadline</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Status</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Effectiveness</th>
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {capaList.map((c, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer" onClick={() => fetchDetail(c.capa_id)}>
                  <td className="py-2.5 px-3 font-mono font-bold text-teal-700">{c.capa_id}</td>
                  <td className="py-2.5 px-3 text-gray-800 font-medium max-w-[200px] truncate">{c.title}</td>
                  <td className="py-2.5 px-3"><Badge className={TYPE_BG[c.action_type] || 'bg-gray-100'}>{c.action_type}</Badge></td>
                  <td className="py-2.5 px-3"><Badge className={PRIORITY_BG[c.priority] || 'bg-gray-100'}>{c.priority}</Badge></td>
                  <td className="py-2.5 px-3 text-gray-600">{c.assigned_to || '—'}</td>
                  <td className="py-2.5 px-3 text-gray-600">{c.deadline ? new Date(c.deadline).toLocaleDateString() : '—'}</td>
                  <td className="py-2.5 px-3"><Badge className={STATUS_BG[c.status] || 'bg-gray-100 text-gray-600'}>{c.status?.replace(/_/g, ' ')}</Badge></td>
                  <td className="py-2.5 px-3"><Badge className={c.effectiveness_status === 'verified_effective' ? 'bg-emerald-100 text-emerald-700' : c.effectiveness_status === 'ineffective' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'}>{c.effectiveness_status?.replace(/_/g, ' ') || 'Pending'}</Badge></td>
                  <td className="py-2.5 px-3">
                    <button className="p-1 text-gray-400 hover:text-teal-600"><Eye size={14} /></button>
                  </td>
                </tr>
              ))}
              {capaList.length === 0 && (
                <tr><td colSpan={9} className="text-center py-8 text-gray-400">No CAPA records found</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <span className="text-[10px] text-gray-400">Showing {capaList.length} of {total} records</span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronLeft size={14} /></button>
            <span className="text-xs text-gray-600 px-2">Page {page} of {pages}</span>
            <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>

      {/* Overdue Actions */}
      {Array.isArray(overdue) && overdue.length > 0 && (
        <div className="bg-white rounded-xl border border-red-200 p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle size={16} className="text-red-600" />
            <h3 className="text-sm font-bold text-red-800">Overdue Actions</h3>
            <Badge className="bg-red-100 text-red-700">{overdue.length} Overdue</Badge>
          </div>
          <div className="space-y-2">
            {overdue.slice(0, 5).map((o, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                <div>
                  <span className="text-xs font-mono font-bold text-red-700">{o.capa_id}</span>
                  <span className="text-xs text-gray-600 ml-2">{o.title}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">Assigned: {o.assigned_to || '—'}</span>
                  <Badge className="bg-red-100 text-red-700">{o.days_overdue || '?'} days overdue</Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CAPA Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-3">CAPA Status Distribution</h3>
          {statusDist.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusDist} dataKey="count" nameKey="status" cx="50%" cy="50%" innerRadius={50} outerRadius={80} strokeWidth={2}>
                  {statusDist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No analytics data available</div>
          )}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-3">Corrective vs Preventive Actions</h3>
          {typeDist.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={typeDist}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="type" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {typeDist.map((_, i) => <Cell key={i} fill={i === 0 ? '#3b82f6' : '#8b5cf6'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No type data available</div>
          )}
        </div>
      </div>

      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-[10px] text-gray-500 flex items-center gap-1.5">
          <Info size={12} className="text-slate-400" />
          Every important CAPA action creates an audit record. A completed action is not automatically effective — evidence and follow-up verification are required.
        </p>
      </div>
    </div>
  )
}
