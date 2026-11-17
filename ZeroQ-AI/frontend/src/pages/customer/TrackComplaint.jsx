import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Search, FileText, Clock, CheckCircle, AlertCircle, ArrowRight, Info } from 'lucide-react'
import api from '../../services/api'

const STATUS_STEPS = ['Submitted', 'Under Review', 'Investigating', 'Resolved']
const STATUS_MAP = {
  submitted: 0,
  under_review: 1,
  investigating: 2,
  investigation_in_progress: 2,
  corrective_action_initiated: 2,
  resolved: 3,
  rejected: 3
}

export default function TrackComplaint() {
  const { complaintId: paramId } = useParams()
  const [searchId, setSearchId] = useState(paramId || '')
  const [complaint, setComplaint] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  React.useEffect(() => { if (paramId) handleSearch(paramId) }, [paramId])

  const handleSearch = async (id) => {
    const cid = id || searchId
    if (!cid) return
    setLoading(true)
    setError('')
    try {
      const res = await api.get(`/api/complaints/${cid}`)
      setComplaint(res.data)
    } catch (err) {
      setError('Complaint not found. Please check the ID and try again.')
      setComplaint(null)
    } finally { setLoading(false) }
  }

  const currentStep = complaint ? (STATUS_MAP[complaint.status] ?? 0) : 0

  return (
    <div className="w-full px-6 lg:px-12 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Track Complaint</h1>
        <p className="text-gray-500 mt-1">Enter your complaint ID to view its current status and progress.</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" placeholder="Enter Complaint ID (e.g., CMP000001)" className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={searchId} onChange={e => setSearchId(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          </div>
          <button onClick={() => handleSearch()} disabled={loading || !searchId} className="px-5 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50">
            {loading ? 'Searching...' : 'Track'}
          </button>
        </div>
        {error && <p className="text-red-600 text-sm mt-3 flex items-center gap-1"><AlertCircle size={14} /> {error}</p>}
      </div>

      {complaint && (
        <div className="space-y-6">
          {/* Progress */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-bold text-gray-900 mb-4">Complaint Progress</h3>
            <div className="flex items-center justify-between">
              {STATUS_STEPS.map((step, i) => (
                <React.Fragment key={i}>
                  <div className="flex flex-col items-center">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${i <= currentStep ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-500'} ${i === currentStep ? 'ring-4 ring-teal-100' : ''}`}>
                      {i < currentStep ? <CheckCircle size={18} /> : i + 1}
                    </div>
                    <span className={`text-xs mt-2 ${i <= currentStep ? 'text-teal-700 font-medium' : 'text-gray-400'}`}>{step}</span>
                  </div>
                  {i < STATUS_STEPS.length - 1 && <div className={`flex-1 h-0.5 mx-2 ${i < currentStep ? 'bg-teal-500' : 'bg-gray-200'}`}></div>}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Details */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-bold text-gray-900 mb-4">Complaint Details</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500 text-xs">Complaint ID</span><p className="font-mono font-bold text-teal-700">{complaint.complaint_id}</p></div>
              <div><span className="text-gray-500 text-xs">Status</span><p className="font-medium text-gray-900 capitalize">{complaint.status?.replace(/_/g, ' ')}</p></div>
              <div><span className="text-gray-500 text-xs">Category</span><p className="text-gray-800">{complaint.category || 'N/A'}</p></div>
              <div><span className="text-gray-500 text-xs">Severity</span><p className="text-gray-800 capitalize">{complaint.reported_severity || 'N/A'}</p></div>
              <div className="col-span-2"><span className="text-gray-500 text-xs">Title</span><p className="text-gray-800 font-medium">{complaint.title || 'N/A'}</p></div>
              <div><span className="text-gray-500 text-xs">Submitted</span><p className="text-gray-800">{complaint.submitted_date ? new Date(complaint.submitted_date).toLocaleDateString() : '—'}</p></div>
              <div><span className="text-gray-500 text-xs">Last Updated</span><p className="text-gray-800">{complaint.last_updated ? new Date(complaint.last_updated).toLocaleDateString() : '—'}</p></div>
            </div>
            {complaint.customer_visible_update && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <span className="text-gray-500 text-xs">Latest Update</span>
                <p className="text-sm text-gray-800 mt-1">{complaint.customer_visible_update}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {!complaint && !error && !loading && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <FileText size={40} className="text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">Enter a complaint ID above to track its progress</p>
        </div>
      )}
    </div>
  )
}

