import React, { useState, useEffect, useCallback } from 'react'
import {
  Search, Filter, Download, Plus, ChevronRight, ChevronLeft,
  Clock, AlertCircle, CheckCircle, Eye, FileText, Shield,
  MessageSquare, Paperclip, ExternalLink, RefreshCw, Info,
  User, Building2, MapPin, Calendar, Package, Hash, DollarSign,
  ArrowRight, Layers, GitBranch, Wrench, X, Send, ChevronDown
} from 'lucide-react'
import api from '../../services/api'
import { useLiveEvents } from '../../hooks/useLiveEvents'
import IncidentVerificationPanel from '../../components/intelligence/IncidentVerificationPanel'
import { SourceBadge } from '../../components/intelligence/ui'

const SEVERITY_STYLES = { critical: 'bg-red-100 text-red-700 border-red-200', high: 'bg-orange-100 text-orange-700 border-orange-200', medium: 'bg-amber-100 text-amber-700 border-amber-200', low: 'bg-green-100 text-green-700 border-green-200' }
const STATUS_STYLES = { submitted: 'bg-blue-100 text-blue-700', under_review: 'bg-amber-100 text-amber-700', investigating: 'bg-purple-100 text-purple-700', resolved: 'bg-green-100 text-green-700', rejected: 'bg-gray-100 text-gray-600' }
// Attachments are private: fetch with the admin's token and open a local blob URL.
async function openAttachment(complaintId, att) {
  try {
    const res = await api.get(`/api/complaints/${complaintId}/attachments/${att.id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    window.alert('Could not open the attachment.')
  }
}

const BORDER_COLORS = { critical: 'border-l-red-500', high: 'border-l-orange-500', medium: 'border-l-amber-500', low: 'border-l-green-500' }

function Badge({ children, className }) { return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${className}`}>{children}</span> }

export default function ComplaintManagement() {
  const [complaints, setComplaints] = useState([])
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [complaintDetail, setComplaintDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [perPage] = useState(20)
  const [pages, setPages] = useState(1)
  const [activeTab, setActiveTab] = useState('overview')
  const [showAllRecords, setShowAllRecords] = useState(true)
  const [filters, setFilters] = useState({ search: '', status: '', category: '', severity: '', record_type: '', product: '', facility: '' })
  const [filterOptions, setFilterOptions] = useState({ products: [], categories: [], facilities: [] })
  const [kpis, setKpis] = useState({})
  const [queueSearch, setQueueSearch] = useState('')
  const [updateStatus, setUpdateStatus] = useState('')
  const [updateCustomerVisible, setUpdateCustomerVisible] = useState('')
  const [updateAdminSeverity, setUpdateAdminSeverity] = useState('medium')
  const [updateNotes, setUpdateNotes] = useState('')
  const [updating, setUpdating] = useState(false)
  const [updateSuccess, setUpdateSuccess] = useState('')

  useEffect(() => { fetchComplaints(); fetchFilters() }, [page, filters, showAllRecords])
  // Live queue: new submissions, finished AI analyses and resolutions refresh the list.
  useLiveEvents(() => { fetchComplaints() }, ['complaint.created', 'analysis.completed', 'complaint.resolved', 'complaint.updated'])

  const fetchComplaints = async () => {
    try {
      setLoading(true)
      const params = { page, per_page: perPage }
      if (filters.search) params.search = filters.search
      if (filters.status) params.status = filters.status
      if (filters.category) params.category = filters.category
      if (filters.severity) params.severity = filters.severity
      if (filters.product) params.product = filters.product
      if (!showAllRecords) params.record_type = 'customer_submitted'
      const res = await api.get('/api/admin/complaints', { params })
      setComplaints(res.data.items || [])
      setTotal(res.data.total || 0)
      setPages(res.data.pages || 1)
      if (res.data.items?.length > 0 && !selectedComplaint) {
        selectComplaint(res.data.items[0])
      }
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

  const selectComplaint = async (complaint) => {
    setSelectedComplaint(complaint)
    setUpdateStatus(complaint.status || 'submitted')
    setUpdateCustomerVisible(complaint.customer_visible_update || '')
    setUpdateAdminSeverity(complaint.admin_severity || complaint.reported_severity || 'medium')
    setUpdateNotes('')
    setUpdateSuccess('')
    setDetailLoading(true)
    try {
      const res = await api.get(`/api/admin/complaints/${complaint.complaint_id}`)
      setComplaintDetail(res.data)
      setUpdateStatus(res.data.status || 'submitted')
      setUpdateCustomerVisible(res.data.customer_visible_update || '')
      setUpdateAdminSeverity(res.data.admin_severity || res.data.reported_severity || 'medium')
    } catch (err) {
      console.error(err)
      setComplaintDetail(complaint)
    } finally { setDetailLoading(false) }
  }

  const handleUpdateComplaint = async () => {
    if (!detail?.complaint_id) return
    setUpdating(true)
    setUpdateSuccess('')
    try {
      await api.put(`/api/admin/complaints/${detail.complaint_id}`, {
        status: updateStatus || detail.status,
        customer_visible_update: updateCustomerVisible,
        notes: updateNotes || `Status updated to ${updateStatus?.replace(/_/g, ' ')}`,
        admin_severity: updateAdminSeverity,
        is_customer_visible: true
      })
      setUpdateSuccess('Status & triage updated successfully!')
      const refreshed = await api.get(`/api/admin/complaints/${detail.complaint_id}`)
      setComplaintDetail(refreshed.data)
      fetchComplaints()
      setTimeout(() => setUpdateSuccess(''), 4000)
    } catch (err) {
      console.error(err)
      alert('Failed to update complaint')
    } finally {
      setUpdating(false)
    }
  }

  const activeCount = complaints.filter(c => c.record_type === 'customer_submitted').length
  const syntheticCount = total - activeCount

  const filteredQueue = complaints.filter(c => {
    if (!queueSearch) return true
    const q = queueSearch.toLowerCase()
    return c.complaint_id?.toLowerCase().includes(q) || c.product_name?.toLowerCase().includes(q) || c.category?.toLowerCase().includes(q)
  })

  const tabs = [
    { id: 'overview', label: 'Overview & Evidence' },
    { id: 'ai', label: 'AI Verification & Resolution' },
    { id: 'investigation', label: 'Investigation & Lab Notes' },
    { id: 'status', label: 'Status & Client Updates' },
    { id: 'audit', label: 'Audit Timeline' }
  ]

  const detail = complaintDetail || selectedComplaint || {}

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">Complaint Management</h1>
            <Badge className="bg-emerald-100 text-emerald-700">ACTIVE QUEUE</Badge>
          </div>
          <p className="text-sm text-gray-500 mt-1">Review, investigate, and manage customer quality complaints across multi-site manufacturing facilities with end-to-end audit traceability.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> Export Dossier (CSV/PDF) <ChevronDown size={12} /></button>
          <button className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700"><Plus size={14} /> Register Complaint (Manual Entry)</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Total Complaints</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{total.toLocaleString()}</div>
          <div className="text-[9px] text-gray-400 mt-0.5">Historical synthetic + active cases</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">New / Submitted</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{complaints.filter(c => c.status === 'submitted').length}</div>
          <div className="text-[9px] text-gray-400 mt-0.5">Awaiting initial triage & routing</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Under Review</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{complaints.filter(c => c.status === 'under_review').length}</div>
          <div className="text-[9px] text-gray-400 mt-0.5">Assigned to plant QA</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Investigation Active</div>
          <div className="text-2xl font-bold text-purple-600 mt-1">{complaints.filter(c => c.status === 'investigating').length}</div>
          <div className="text-[9px] text-gray-400 mt-0.5">Shop floor & lab testing</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Resolved / Closed</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{complaints.filter(c => c.status === 'resolved').length}</div>
          <div className="text-[9px] text-gray-400 mt-0.5">Root cause closure</div>
        </div>
      </div>

      {/* Dual Data Topology */}
      <div className="bg-teal-50 border border-teal-200 rounded-lg px-4 py-2.5 mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers size={14} className="text-teal-600" />
          <span className="text-xs text-teal-800"><strong>Dual Data Topology Active:</strong> Currently distinguishing historical records from newly submitted customer intake cases.</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setShowAllRecords(true)} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${showAllRecords ? 'bg-white text-teal-700 shadow-sm' : 'text-teal-600 hover:bg-teal-100'}`}>Show All</button>
          <button onClick={() => setShowAllRecords(false)} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${!showAllRecords ? 'bg-teal-600 text-white shadow-sm' : 'text-teal-600 hover:bg-teal-100'}`}>Only New Active</button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-gray-100 rounded-lg px-3 py-1.5 min-w-[200px]">
            <Search size={14} className="text-gray-400 mr-2" />
            <input placeholder="Search Complaint ID, Product..." className="bg-transparent text-sm focus:outline-none w-full" value={filters.search} onChange={e => setFilters({...filters, search: e.target.value})} />
          </div>
          <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.status} onChange={e => setFilters({...filters, status: e.target.value})}>
            <option value="">All Statuses</option>
            <option value="submitted">Submitted</option>
            <option value="under_review">Under Review</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
          </select>
          <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.category} onChange={e => setFilters({...filters, category: e.target.value})}>
            <option value="">All Categories</option>
            {(Array.isArray(filterOptions?.categories) ? filterOptions.categories : []).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white" value={filters.severity} onChange={e => setFilters({...filters, severity: e.target.value})}>
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button onClick={fetchComplaints} className="px-3 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-700 flex items-center gap-1"><Filter size={12} /> Apply</button>
        </div>
        <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-400">
          {filters.search && <span className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded-full flex items-center gap-1">Search: {filters.search} <X size={10} className="cursor-pointer" onClick={() => setFilters({...filters, search: ''})} /></span>}
          <span>Showing {complaints.length} of {total} complaints</span>
        </div>
      </div>

      {/* Split Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* LEFT: Complaint Queue */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-3 border-b border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-gray-900">Complaint Queue</h3>
                <Badge className="bg-teal-100 text-teal-700">{complaints.length} Items</Badge>
              </div>
              <div className="text-[10px] text-gray-400">Sorted: Newest</div>
            </div>
            <div className="flex items-center bg-gray-50 rounded-lg px-2.5 py-1.5">
              <Search size={13} className="text-gray-400 mr-2" />
              <input placeholder="Quick filter ID, product, category..." className="bg-transparent text-xs focus:outline-none w-full" value={queueSearch} onChange={e => setQueueSearch(e.target.value)} />
            </div>
          </div>

          <div className="overflow-y-auto max-h-[600px]">
            {loading ? (
              <div className="p-8 text-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div></div>
            ) : filteredQueue.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No complaints match your filters</div>
            ) : (
              filteredQueue.map((c) => (
                <div
                  key={c.id}
                  onClick={() => selectComplaint(c)}
                  className={`p-3 border-b border-gray-50 cursor-pointer transition-colors border-l-4 ${
                    selectedComplaint?.id === c.id ? 'bg-teal-50 border-l-teal-500' : `hover:bg-gray-50 ${BORDER_COLORS[c.reported_severity] || 'border-l-gray-200'}`
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono font-bold text-teal-700">{c.complaint_id}</span>
                    <div className="flex items-center gap-1">
                      <Badge className={SEVERITY_STYLES[c.reported_severity] || 'bg-gray-100 text-gray-600'}>{c.reported_severity ? c.reported_severity.toUpperCase() : 'NOT REPORTED'}</Badge>
                      <Badge className={STATUS_STYLES[c.status] || 'bg-gray-100 text-gray-600'}>{c.status?.replace(/_/g, ' ')}</Badge>
                    </div>
                  </div>
                  <div className="text-xs font-medium text-gray-800">{c.product_name || 'Unknown Product'}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">{c.category || 'N/A'}</div>
                  {(c.data_origin === 'synthetic' || c.data_origin === 'test') && (
                    <span className={`inline-block mt-1 mr-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${c.data_origin === 'test' ? 'bg-violet-100 text-violet-800' : 'bg-slate-100 text-slate-600'}`}
                      title={c.data_origin === 'test' ? 'Submitted by a test account — excluded from real-world metrics and training' : 'Imported synthetic record'}>
                      {c.data_origin === 'test' ? 'TEST' : 'SYNTHETIC'}
                    </span>
                  )}
                  {c.ai && (
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      <SourceBadge source={c.ai.source} />
                      {c.ai.language && c.ai.language !== 'English' && <span className="text-[10px] text-gray-500">{c.ai.language}</span>}
                      {c.ai.low_confidence && <span className="text-[10px] font-semibold text-amber-700">verify</span>}
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px] text-gray-400">
                      {c.submitted_date ? new Date(c.submitted_date).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                    </span>
                    {c.record_type === 'historical_synthetic' && (
                      <Badge className="bg-slate-100 text-slate-500 border border-slate-200">Historical Record</Badge>
                    )}
                    {c.record_type === 'customer_submitted' && (
                      <Badge className="bg-emerald-50 text-emerald-600">Customer Submitted</Badge>
                    )}
                  </div>
                  {c.assigned_to && <div className="text-[10px] text-gray-400 mt-1">Assigned: {c.assigned_to}</div>}
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          <div className="p-3 border-t border-gray-100 flex items-center justify-between">
            <span className="text-[10px] text-gray-400">Showing {(page - 1) * perPage + 1}-{Math.min(page * perPage, total)} of {total}</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronLeft size={14} /></button>
              <span className="text-xs text-gray-600 px-2">{page}</span>
              <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronRight size={14} /></button>
            </div>
          </div>
        </div>

        {/* RIGHT: Complaint Details */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-gray-200 overflow-hidden">
          {!selectedComplaint ? (
            <div className="flex items-center justify-center h-96 text-gray-400">
              <div className="text-center">
                <FileText size={40} className="mx-auto mb-3 text-gray-300" />
                <p className="text-sm font-medium">Select a complaint to view details</p>
                <p className="text-xs mt-1">Choose from the queue on the left</p>
              </div>
            </div>
          ) : (
            <>
              {/* Detail Header */}
              <div className="p-4 border-b border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold font-mono text-gray-900">{detail.complaint_id}</span>
                    <Badge className={`${detail.record_type === 'customer_submitted' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {detail.record_type === 'customer_submitted' ? 'Customer Submitted' : 'Historical'}
                    </Badge>
                    <Badge className={SEVERITY_STYLES[detail.reported_severity] || 'bg-gray-100 text-gray-600'}>
                      {detail.reported_severity ? `${detail.reported_severity.toUpperCase()} SEVERITY` : 'SEVERITY NOT REPORTED'}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-[10px] text-gray-400">
                  <span className="flex items-center gap-1"><Clock size={10} /> Logged {detail.submitted_date ? new Date(detail.submitted_date).toLocaleString() : '—'}</span>
                  {detail.assigned_to && <span className="flex items-center gap-1"><User size={10} /> Assigned: {detail.assigned_to}</span>}
                </div>

                {/* Severity Comparison */}
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div className="bg-gray-50 rounded-lg p-2.5">
                    <div className="text-[9px] font-semibold text-gray-500 uppercase">Customer-Reported</div>
                    <Badge className={`mt-1 ${SEVERITY_STYLES[detail.reported_severity] || 'bg-gray-100'}`}>{detail.reported_severity || 'N/A'}</Badge>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2.5">
                    <div className="text-[9px] font-semibold text-gray-500 uppercase">Admin Assessed</div>
                    <Badge className={`mt-1 ${SEVERITY_STYLES[detail.admin_severity] || 'bg-gray-100 text-gray-500'}`}>{detail.admin_severity || 'Pending Assessment'}</Badge>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="border-b border-gray-100 px-4">
                <div className="flex gap-0 overflow-x-auto">
                  {tabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
                        activeTab === tab.id ? 'border-teal-600 text-teal-700' : 'border-transparent text-gray-500 hover:text-gray-700'
                      }`}
                    >{tab.label}</button>
                  ))}
                </div>
              </div>

              {/* Tab Content */}
              <div className={`p-4 overflow-y-auto ${activeTab === 'ai' ? 'max-h-[75vh]' : 'max-h-[480px]'}`}>
                {detailLoading ? (
                  <div className="py-8 text-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div></div>
                ) : activeTab === 'ai' ? (
                  <IncidentVerificationPanel complaintId={detail.complaint_id} onResolved={() => { fetchComplaints(); selectComplaint(detail) }} />
                ) : activeTab === 'overview' ? (
                  <div className="space-y-4">
                    {/* Customer & Production Batch */}
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-xs font-bold text-gray-900 uppercase">Customer Account & Production Batch</h4>
                        {detail.record_type === 'customer_submitted' && <Badge className="bg-emerald-100 text-emerald-700 flex items-center gap-1"><CheckCircle size={10} /> Verified Enterprise Client</Badge>}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-[10px] text-gray-500 mb-0.5">Reporting Client</div>
                          <div className="text-sm font-semibold text-gray-900">{detail.customer_name || detail.customer_organization || 'N/A'}</div>
                          {detail.customer_email && <div className="text-[10px] text-gray-400 mt-0.5">{detail.customer_email}</div>}
                        </div>
                        <div>
                          <div className="text-[10px] text-gray-500 mb-0.5">Target Production Batch</div>
                          <div className="text-sm font-semibold text-gray-900">{detail.batch_id || 'N/A'}</div>
                          {detail.facility_name && <div className="text-[10px] text-gray-400 mt-0.5">{detail.facility_name}</div>}
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-4 mt-3 pt-3 border-t border-gray-200">
                        <div>
                          <div className="text-[10px] text-gray-500">Incident Date</div>
                          <div className="text-xs font-semibold text-gray-800">{detail.date_of_issue ? new Date(detail.date_of_issue).toLocaleDateString() : '—'}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-gray-500">Intake Date</div>
                          <div className="text-xs font-semibold text-gray-800">{detail.submitted_date ? new Date(detail.submitted_date).toLocaleDateString() : '—'}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-gray-500">Product</div>
                          <div className="text-xs font-semibold text-gray-800">{detail.product_name || 'N/A'}</div>
                        </div>
                      </div>
                    </div>

                    {/* Active Status & Triage Controller */}
                    <div className="bg-white border-2 border-teal-200 rounded-xl p-4 shadow-sm">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Wrench size={15} className="text-teal-600" />
                          <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Quality Triage & Workflow Transition</h4>
                        </div>
                        {updateSuccess && (
                          <span className="text-xs font-medium text-emerald-600 flex items-center gap-1 animate-pulse">
                            <CheckCircle size={13} /> {updateSuccess}
                          </span>
                        )}
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                        <div>
                          <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Workflow Stage</label>
                          <select
                            value={updateStatus}
                            onChange={e => setUpdateStatus(e.target.value)}
                            className="w-full text-xs border border-gray-300 rounded-lg px-2.5 py-2 bg-white font-medium text-gray-800 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                          >
                            <option value="submitted">1. Submitted (Pending Review)</option>
                            <option value="under_review">2. Under Review (QA Triage)</option>
                            <option value="investigation_in_progress">3. Investigating (Lab & Shop Floor)</option>
                            <option value="corrective_action_initiated">4. CAPA Initiated</option>
                            <option value="resolved">5. Resolved (Action Completed)</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Admin Assessed Severity</label>
                          <select
                            value={updateAdminSeverity}
                            onChange={e => setUpdateAdminSeverity(e.target.value)}
                            className="w-full text-xs border border-gray-300 rounded-lg px-2.5 py-2 bg-white font-medium text-gray-800 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                          >
                            <option value="low">Low Severity</option>
                            <option value="medium">Medium Severity</option>
                            <option value="high">High Severity</option>
                            <option value="critical">Critical Severity</option>
                          </select>
                        </div>
                      </div>

                      <div className="mb-3">
                        <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">
                          Customer-Visible Status Update (Surfaced to Client Tracking Portal)
                        </label>
                        <input
                          type="text"
                          placeholder="e.g., Retain samples inspected; QA team verifying sealing temperature logs."
                          value={updateCustomerVisible}
                          onChange={e => setUpdateCustomerVisible(e.target.value)}
                          className="w-full text-xs border border-gray-300 rounded-lg px-3 py-2 text-gray-800 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                        />
                      </div>

                      <div className="mb-3">
                        <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">
                          Internal QA Triage Notes (Audit Trail Only)
                        </label>
                        <textarea
                          rows={2}
                          placeholder="Internal technical notes, lab sample numbers, or root cause hypothesis..."
                          value={updateNotes}
                          onChange={e => setUpdateNotes(e.target.value)}
                          className="w-full text-xs border border-gray-300 rounded-lg px-3 py-2 text-gray-800 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                        />
                      </div>

                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={handleUpdateComplaint}
                          disabled={updating}
                          className="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5 transition-colors shadow-sm"
                        >
                          {updating ? <RefreshCw size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                          {updating ? 'Saving Changes...' : 'Apply Status & Notify Customer'}
                        </button>
                      </div>
                    </div>

                    {/* Verbatim Narrative */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-xs font-bold text-gray-900 uppercase">Verbatim Customer Incident Narrative</h4>
                        <Badge className="bg-gray-100 text-gray-500">{detail.record_type === 'customer_submitted' ? 'Portal Direct Intake' : 'Historical Record'}</Badge>
                      </div>
                      <h5 className="text-sm font-bold text-gray-900 mb-2 leading-snug">"{detail.title || 'No title provided'}"</h5>
                      <p className="text-sm text-gray-600 leading-relaxed">{detail.description || 'No description available.'}</p>
                    </div>

                    {/* Attachments */}
                    {detail.attachments?.length > 0 && (
                      <div className="bg-white border border-gray-200 rounded-lg p-4">
                        <h4 className="text-xs font-bold text-gray-900 uppercase mb-3">Supporting Evidence & Attachments</h4>
                        <div className="space-y-2">
                          {detail.attachments.map((att, i) => (
                            <div key={i} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                              <Paperclip size={14} className="text-gray-400" />
                              <div className="flex-1">
                                <div className="text-xs font-medium text-gray-700">{att.original_filename}</div>
                                <div className="text-[10px] text-gray-400">{(att.file_size / 1024).toFixed(1)} KB</div>
                              </div>
                              <button type="button" onClick={() => openAttachment(detail.complaint_id, att)}
                                aria-label={`Open ${att.original_filename}`}
                                className="p-1 rounded text-teal-600 hover:bg-teal-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500">
                                <Eye size={14} aria-hidden="true" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2 pt-2">
                      <button className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-700"><GitBranch size={13} /> Start Lab Investigation</button>
                      <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50"><Wrench size={13} /> Link CAPA Ticket</button>
                      <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50"><Download size={13} /> Export Dossier</button>
                    </div>
                  </div>
                ) : activeTab === 'investigation' ? (
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold text-gray-900 uppercase">Investigation & Lab Notes</h4>
                    {detail.investigations?.length > 0 ? (
                      detail.investigations.map((inv, i) => (
                        <div key={i} className="bg-gray-50 rounded-lg p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-mono font-bold text-gray-700">{inv.investigation_id}</span>
                            <Badge className={inv.status === 'closed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}>{inv.status}</Badge>
                          </div>
                          <p className="text-xs text-gray-600">{inv.title}</p>
                          {inv.root_cause_category && (
                            <div className="mt-2 text-xs">
                              <span className="text-gray-500">Root Cause: </span>
                              <span className="font-medium text-gray-800">{inv.root_cause_category}</span>
                              {inv.is_root_cause_verified && <CheckCircle size={12} className="inline ml-1 text-emerald-500" />}
                            </div>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-gray-400">
                        <Shield size={24} className="mx-auto mb-2" />
                        <p className="text-sm">No investigations started yet</p>
                      </div>
                    )}
                  </div>
                ) : activeTab === 'status' ? (
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold text-gray-900 uppercase">Status History & Client Updates</h4>
                    {detail.status_history?.length > 0 ? (
                      detail.status_history.map((sh, i) => (
                        <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                          <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
                            <ArrowRight size={14} className="text-teal-600" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Badge className={STATUS_STYLES[sh.old_status]}>{sh.old_status?.replace(/_/g, ' ')}</Badge>
                              <ArrowRight size={10} className="text-gray-400" />
                              <Badge className={STATUS_STYLES[sh.new_status]}>{sh.new_status?.replace(/_/g, ' ')}</Badge>
                            </div>
                            <div className="text-[10px] text-gray-500 mt-1">
                              {sh.changed_by} • {sh.changed_at ? new Date(sh.changed_at).toLocaleString() : '—'}
                              {sh.is_customer_visible && <Badge className="ml-1 bg-blue-50 text-blue-600">Customer Visible</Badge>}
                            </div>
                            {sh.notes && <p className="text-xs text-gray-600 mt-1.5">{sh.notes}</p>}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-gray-400">
                        <MessageSquare size={24} className="mx-auto mb-2" />
                        <p className="text-sm">No status updates yet</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold text-gray-900 uppercase">Audit Timeline</h4>
                    <div className="text-center py-8 text-gray-400">
                      <Clock size={24} className="mx-auto mb-2" />
                      <p className="text-sm">Audit trail records all administrative actions</p>
                      <p className="text-xs mt-1">Status changes, assignments, and notes are tracked automatically</p>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
