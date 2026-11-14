import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Search, Filter, Eye, Clock, CheckCircle, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../../services/api'

const SEVERITY_STYLES = { critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700', medium: 'bg-amber-100 text-amber-700', low: 'bg-green-100 text-green-700' }
const STATUS_STYLES = { submitted: 'bg-blue-100 text-blue-700', under_review: 'bg-amber-100 text-amber-700', investigating: 'bg-purple-100 text-purple-700', resolved: 'bg-green-100 text-green-700', rejected: 'bg-gray-100 text-gray-600' }

export default function MyComplaints() {
  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [search, setSearch] = useState('')

  useEffect(() => { fetchComplaints() }, [page])

  const fetchComplaints = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/complaints/', { params: { page, per_page: 10 } })
      setComplaints(res.data?.items || res.data || [])
      setTotal(res.data?.total || 0)
      setPages(res.data?.pages || 1)
    } catch (err) {
      console.error(err)
    } finally { setLoading(false) }
  }

  const filtered = complaints.filter(c => {
    if (!search) return true
    const q = search.toLowerCase()
    return c.complaint_id?.toLowerCase().includes(q) || c.title?.toLowerCase().includes(q) || c.category?.toLowerCase().includes(q)
  })

  return (
    <div className="w-full px-6 lg:px-12 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Complaints</h1>
          <p className="text-gray-500 mt-1">View and manage all your submitted complaints</p>
        </div>
        <Link to="/customer/submit-complaint" className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700">+ New Complaint</Link>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <div className="flex items-center bg-gray-100 rounded-lg px-3 py-2">
          <Search size={16} className="text-gray-400 mr-2" />
          <input placeholder="Search complaints..." className="bg-transparent text-sm focus:outline-none w-full" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-teal-600 mx-auto"></div></div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <FileText size={40} className="text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No complaints found</p>
            <Link to="/customer/submit-complaint" className="inline-block mt-3 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700">Submit Your First Complaint</Link>
          </div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Complaint ID</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Title</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Category</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Severity</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Date</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 px-4 font-mono font-medium text-teal-700">{c.complaint_id}</td>
                    <td className="py-3 px-4 text-gray-800 max-w-[200px] truncate">{c.title || 'N/A'}</td>
                    <td className="py-3 px-4 text-gray-600">{c.category || 'N/A'}</td>
                    <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${SEVERITY_STYLES[c.reported_severity] || 'bg-gray-100 text-gray-600'}`}>{c.reported_severity || 'N/A'}</span></td>
                    <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${STATUS_STYLES[c.status] || 'bg-gray-100 text-gray-600'}`}>{c.status?.replace(/_/g, ' ') || 'N/A'}</span></td>
                    <td className="py-3 px-4 text-gray-500">{c.submitted_date ? new Date(c.submitted_date).toLocaleDateString() : '—'}</td>
                    <td className="py-3 px-4">
                      <Link to={`/customer/track-complaint/${c.complaint_id}`} className="text-teal-600 hover:text-teal-700"><Eye size={16} /></Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between p-4 border-t border-gray-100">
              <span className="text-xs text-gray-400">{total} total complaints</span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronLeft size={16} /></button>
                <span className="text-xs text-gray-600 px-2">Page {page} of {pages}</span>
                <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronRight size={16} /></button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

