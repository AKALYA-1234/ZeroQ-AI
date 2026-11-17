import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Upload, Package, AlertTriangle, Calendar, MapPin,
  Send, X, ChevronDown, Info, CheckCircle, Paperclip, Trash2
} from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../context/AuthContext'

const CATEGORIES = [
  'Packaging Defect',
  'Sensory Defect',
  'Physical Defect',
  'Foreign Matter / Contamination',
  'Weight / Quantity',
  'Process-related Defect',
  'Infestation',
  'Other Customer Concern'
]
const SEVERITIES = [
  { value: 'low', label: 'Low', desc: 'Minor issue, no safety impact', color: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'medium', label: 'Medium', desc: 'Moderate issue, limited impact', color: 'bg-amber-100 text-amber-700 border-amber-300' },
  { value: 'high', label: 'High', desc: 'Significant issue, major impact', color: 'bg-orange-100 text-orange-700 border-orange-300' },
  { value: 'critical', label: 'Critical', desc: 'Severe issue, safety risk', color: 'bg-red-100 text-red-700 border-red-300' }
]

export default function SubmitComplaint() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [products, setProducts] = useState([])
  const [submitted, setSubmitted] = useState(false)
  const [complaintId, setComplaintId] = useState('')
  const [files, setFiles] = useState([])
  const [form, setForm] = useState({
    product_id: '', title: '', description: '', category: '',
    reported_severity: '', purchase_date: '', date_of_issue: '',
    place_of_purchase: '', customer_name: user?.full_name || '',
    customer_contact: '', customer_organization: '', batch_number: ''
  })

  React.useEffect(() => {
    api.get('/api/products').then(res => setProducts(res.data?.items || res.data || [])).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('product_id', parseInt(form.product_id) || 1)
      fd.append('title', form.title)
      fd.append('description', form.description)
      fd.append('category', form.category)
      fd.append('reported_severity', form.reported_severity)
      if (form.batch_number) fd.append('batch_number', form.batch_number)
      if (form.purchase_date) fd.append('purchase_date', form.purchase_date)
      if (form.date_of_issue) fd.append('date_of_issue', form.date_of_issue)
      if (form.place_of_purchase) fd.append('place_of_purchase', form.place_of_purchase)
      files.forEach(f => fd.append('files', f))

      const res = await api.post('/api/complaints/', fd)
      setComplaintId(res.data?.complaint_id || '')
      setSubmitted(true)
    } catch (err) {
      console.error(err)
      alert(err.response?.data?.detail || 'Failed to submit complaint. Please try again.')
    } finally { setLoading(false) }
  }

  if (submitted) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle size={32} className="text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Complaint Submitted Successfully</h2>
          <p className="text-gray-500 mb-2">Your complaint has been registered with ID:</p>
          <p className="text-lg font-mono font-bold text-teal-600 mb-6">{complaintId}</p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate(`/customer/track-complaint/${complaintId}`)} className="px-5 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700">Track Status</button>
            <button onClick={() => navigate('/customer/my-complaints')} className="px-5 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">View My Complaints</button>
            <button onClick={() => { setSubmitted(false); setForm({ ...form, title: '', description: '', category: '', reported_severity: '' }) }} className="px-5 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">Submit Another</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full px-6 lg:px-12 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Submit a Complaint</h1>
        <p className="text-gray-500 mt-1">Report a product quality issue. Our team will investigate and respond promptly.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Product Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Product *</label>
              <select required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.product_id} onChange={e => setForm({...form, product_id: e.target.value})}>
                <option value="">Select Product</option>
                {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Batch ID (if known)</label>
              <input type="text" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.batch_number} onChange={e => setForm({...form, batch_number: e.target.value})} placeholder="e.g., BAT000001" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Complaint Details</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Complaint Title *</label>
              <input type="text" required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.title} onChange={e => setForm({...form, title: e.target.value})} placeholder="Brief summary of the issue" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
              <textarea required rows={5} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none" value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="Provide a detailed description of the issue..." />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category *</label>
                <select required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.category} onChange={e => setForm({...form, category: e.target.value})}>
                  <option value="">Select Category</option>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity *</label>
                <select required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.reported_severity} onChange={e => setForm({...form, reported_severity: e.target.value})}>
                  <option value="">Select Severity</option>
                  {SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label} — {s.desc}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date of Issue</label>
                <input type="date" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.date_of_issue} onChange={e => setForm({...form, date_of_issue: e.target.value})} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Purchase Date</label>
                <input type="date" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={form.purchase_date} onChange={e => setForm({...form, purchase_date: e.target.value})} />
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={() => navigate('/customer/home')} className="px-5 py-2.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50">Cancel</button>
          <button type="submit" disabled={loading} className="px-6 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 flex items-center gap-2">
            <Send size={14} /> {loading ? 'Submitting...' : 'Submit Complaint'}
          </button>
        </div>
      </form>
    </div>
  )
}

