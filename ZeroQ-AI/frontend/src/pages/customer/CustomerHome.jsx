import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { complaintService } from '../../services/complaintService'
import {
  FileText, Search, CheckCircle, Clock, AlertCircle,
  ArrowRight, Mail, Phone, Plus, Eye, Loader2,
  Shield, Upload, BarChart3, ChevronRight, Zap, Brain, Sparkles
} from 'lucide-react'

const StatusBadge = ({ status }) => {
  const styles = {
    submitted: 'bg-gray-100 text-gray-700',
    under_review: 'bg-blue-100 text-blue-700',
    investigation_in_progress: 'bg-orange-100 text-orange-700',
    corrective_action_initiated: 'bg-purple-100 text-purple-700',
    resolved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
  }
  const labels = {
    submitted: 'Submitted',
    under_review: 'Under Review',
    investigation_in_progress: 'Investigation',
    corrective_action_initiated: 'Action Initiated',
    resolved: 'Resolved',
    rejected: 'Rejected',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-700'}`}>
      {labels[status] || status}
    </span>
  )
}

export default function CustomerHome() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [summary, setSummary] = useState({ total: 0, under_review: 0, resolved: 0 })
  const [recentComplaints, setRecentComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [trackId, setTrackId] = useState('')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summaryRes, recentRes] = await Promise.all([
          complaintService.getSummary(),
          complaintService.getRecent()
        ])
        setSummary(summaryRes.data)
        setRecentComplaints(recentRes.data)
      } catch (err) {
        console.error('Failed to load dashboard data:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const firstName = user?.full_name ? user.full_name.split(' ')[0] : 'Customer'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top notification bar */}
      <div className="bg-slate-800 text-white px-4 py-2.5 text-sm">
        <div className="w-full px-4 lg:px-8 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span>👋</span>
            <span>Welcome back, {firstName}. You have <strong className="text-teal-400">{summary.total} complaints</strong> currently progressing through quality inspection.</span>
          </div>
          <Link to="/customer/my-complaints" className="text-teal-400 hover:text-teal-300 text-sm font-medium flex items-center space-x-1">
            <span>View In-Progress Complaints</span><ChevronRight size={14} />
          </Link>
        </div>
      </div>

      <div className="w-full px-6 lg:px-12 py-8">
        {/* Welcome to ZeroQ AI Banner */}
        <div className="bg-white rounded-2xl border border-gray-200 p-8 mb-8 relative overflow-hidden">
          <div className="mb-2">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-teal-100 text-teal-700 border border-teal-200">
              ✓ VERIFIED CUSTOMER PORTAL • QUALITY ASSURANCE PORTAL
            </span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">Welcome to ZeroQ AI</h1>
          <p className="text-gray-600 text-lg mb-6 max-w-3xl">
            Your feedback helps us uphold strict manufacturing tolerances and improve product quality. Submit a complaint, upload laboratory or inspection evidence, and trace resolution workflows in real time.
          </p>

          {/* Feature badges row */}
          <div className="flex flex-wrap gap-4 mb-2">
            <div className="flex items-center space-x-2 bg-slate-50 rounded-lg px-4 py-2 border border-slate-200">
              <Shield size={16} className="text-teal-600" />
              <div>
                <div className="text-xs font-semibold text-gray-700">DEDICATED CASE REVIEW</div>
                <div className="text-xs text-gray-500">Assigned to Specialist Teams</div>
              </div>
            </div>
            <div className="flex items-center space-x-2 bg-slate-50 rounded-lg px-4 py-2 border border-slate-200">
              <Upload size={16} className="text-teal-600" />
              <div>
                <div className="text-xs font-semibold text-gray-700">DIRECT FILE UPLOADS</div>
                <div className="text-xs text-gray-500">High-res photos & evidence</div>
              </div>
            </div>
            <div className="flex items-center space-x-2 bg-slate-50 rounded-lg px-4 py-2 border border-slate-200">
              <BarChart3 size={16} className="text-teal-600" />
              <div>
                <div className="text-xs font-semibold text-gray-700">TRANSPARENT TRACKING</div>
                <div className="text-xs text-gray-500">Real-time timeline updates</div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions Row: Submit, AI Predictor, and Track */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Submit Complaint Card */}
          <div className="card p-6 hover:shadow-md transition-shadow flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between mb-4">
                <div className="bg-teal-100 p-3 rounded-xl">
                  <FileText size={24} className="text-teal-600" />
                </div>
                <span className="text-xs font-semibold text-teal-600 bg-teal-50 px-2 py-1 rounded">SUBMISSION</span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Submit a Complaint</h3>
              <p className="text-gray-600 text-sm mb-4">
                Report a product defect, packaging issue, or quality discrepancy with inspection photos, batch details, and comments.
              </p>
              <div className="space-y-1.5 mb-4 text-xs text-gray-500">
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Upload photos & inspection evidence</span></div>
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Batch and lot verification</span></div>
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Direct ticket escalation</span></div>
              </div>
            </div>
            <Link to="/customer/submit-complaint" className="inline-flex items-center space-x-2 bg-teal-600 text-white px-4 py-2.5 rounded-lg font-semibold hover:bg-teal-700 transition-colors w-full justify-center text-sm">
              <span>Submit Complaint</span><ArrowRight size={16} />
            </Link>
          </div>

          {/* AI Risk Predictor Card */}
          <div className="card p-6 hover:shadow-md transition-shadow border-teal-200 bg-gradient-to-b from-teal-50/40 to-white flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between mb-4">
                <div className="bg-teal-600 p-3 rounded-xl text-white shadow-sm shadow-teal-700/20">
                  <Brain size={24} />
                </div>
                <span className="text-xs font-bold text-teal-800 bg-teal-100 px-2.5 py-1 rounded-full border border-teal-200 flex items-center space-x-1">
                  <Sparkles size={11} className="mr-0.5" />
                  <span>AI ML MODEL</span>
                </span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">AI Risk Predictor</h3>
              <p className="text-gray-600 text-sm mb-4">
                Ask conversational questions to forecast 90-day complaint risk and evaluate batch telemetry using our trained XGBoost model.
              </p>
              <div className="space-y-1.5 mb-4 text-xs text-gray-500">
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Natural language parameter extraction</span></div>
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Trained XGBoost probability calculation</span></div>
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Contributing factor breakdown & history</span></div>
              </div>
            </div>
            <Link to="/customer/query-prediction" className="inline-flex items-center space-x-2 bg-slate-900 text-white px-4 py-2.5 rounded-lg font-semibold hover:bg-slate-800 transition-colors w-full justify-center text-sm">
              <span>Launch AI Predictor</span><ArrowRight size={16} />
            </Link>
          </div>

          {/* Track Complaint Card */}
          <div className="card p-6 hover:shadow-md transition-shadow flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between mb-4">
                <div className="bg-teal-100 p-3 rounded-xl">
                  <Search size={24} className="text-teal-600" />
                </div>
                <span className="text-xs font-semibold text-teal-600 bg-teal-50 px-2 py-1 rounded">INSTANT STATUS</span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Track Your Complaint</h3>
              <p className="text-gray-600 text-sm mb-4">
                Check QA notes, root-cause investigation milestones, and resolution progress using your Complaint Reference ID.
              </p>
              <div className="flex items-center space-x-2 mb-4">
                <input
                  type="text"
                  value={trackId}
                  onChange={e => setTrackId(e.target.value)}
                  placeholder="e.g., CMP000001"
                  className="flex-1 input-field text-sm"
                />
                <button
                  onClick={() => trackId && navigate(`/customer/track-complaint/${trackId}`)}
                  className="bg-teal-600 text-white px-3.5 py-2.5 rounded-lg font-medium hover:bg-teal-700 transition-colors flex items-center space-x-1 text-sm"
                >
                  <Search size={15} /><span>Track</span>
                </button>
              </div>
              <div className="space-y-1.5 mb-4 text-xs text-gray-500">
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>Live milestone tracking & closure notes</span></div>
                <div className="flex items-center space-x-1"><CheckCircle size={12} className="text-teal-500" /><span>CAPA verification evidence</span></div>
              </div>
            </div>
            <Link to="/customer/track-complaint" className="text-teal-600 hover:text-teal-700 text-sm font-medium flex items-center space-x-1 justify-center py-2">
              <span>Open Tracking Portal</span><ArrowRight size={14} />
            </Link>
          </div>
        </div>

        {/* Complaints Summary */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900">Your Complaints Summary</h2>
            <span className="text-sm text-gray-500">All activity for {user?.full_name}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {loading ? (
              Array(3).fill(0).map((_, i) => (
                <div key={i} className="card p-6 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-24 mb-3"></div>
                  <div className="h-10 bg-gray-200 rounded w-16"></div>
                </div>
              ))
            ) : (
              <>
                <div className="card p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Complaints</span>
                    <div className="bg-blue-100 p-2 rounded-lg"><FileText size={18} className="text-blue-600" /></div>
                  </div>
                  <div className="text-4xl font-bold text-gray-900 mb-1">{String(summary.total).padStart(2, '0')}</div>
                  <div className="text-xs text-gray-500">Total Complaints Filed</div>
                </div>
                <div className="card p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Under Review</span>
                      <span className="w-2 h-2 bg-orange-400 rounded-full"></span>
                    </div>
                    <div className="bg-orange-100 p-2 rounded-lg"><Clock size={18} className="text-orange-600" /></div>
                  </div>
                  <div className="text-4xl font-bold text-gray-900 mb-1">{String(summary.under_review).padStart(2, '0')}</div>
                  <div className="text-xs text-orange-600 font-medium">Active Inspection</div>
                </div>
                <div className="card p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Resolved</span>
                    <div className="bg-green-100 p-2 rounded-lg"><CheckCircle size={18} className="text-green-600" /></div>
                  </div>
                  <div className="text-4xl font-bold text-gray-900 mb-1">{String(summary.resolved).padStart(2, '0')}</div>
                  <div className="text-xs text-green-600 font-medium">Closed & Completed</div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Recent Complaints */}
        <div className="card mb-8">
          <div className="flex items-center justify-between p-6 border-b border-gray-100">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Recent Complaints</h2>
              <p className="text-sm text-gray-500 mt-0.5">Overview of your recent product quality tickets and evaluation lifecycle</p>
            </div>
            <Link to="/customer/my-complaints" className="text-sm text-teal-600 hover:text-teal-700 font-medium flex items-center space-x-1">
              <span>View All Complaints</span><ChevronRight size={16} />
            </Link>
          </div>
          {loading ? (
            <div className="p-12 text-center"><Loader2 className="animate-spin text-teal-600 mx-auto" size={32} /></div>
          ) : recentComplaints.length === 0 ? (
            <div className="p-12 text-center">
              <FileText size={48} className="text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-700 mb-2">No complaints yet</h3>
              <p className="text-gray-500 mb-6">Submit your first complaint to get started.</p>
              <Link to="/customer/submit-complaint" className="btn-primary inline-flex items-center space-x-2">
                <Plus size={18} /><span>Submit Complaint</span>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    {['COMPLAINT ID', 'PRODUCT', 'COMPLAINT CATEGORY', 'SUBMITTED DATE', 'STATUS', 'ACTION'].map(h => (
                      <th key={h} className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {recentComplaints.map(c => (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-2">
                          <div className="w-2 h-2 bg-teal-500 rounded-full"></div>
                          <span className="text-sm font-medium text-teal-600">{c.complaint_id}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">{c.product_name}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        <div className="flex items-center space-x-1">
                          <span className="text-gray-400">⊕</span><span>{c.category}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{new Date(c.submitted_date).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })}</td>
                      <td className="px-6 py-4"><StatusBadge status={c.status} /></td>
                      <td className="px-6 py-4">
                        <Link to={`/customer/track-complaint/${c.complaint_id}`} className="inline-flex items-center space-x-1 text-sm text-teal-600 hover:text-teal-700 font-medium">
                          <Eye size={14} /><span>View Details</span>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-6 py-3 border-t border-gray-100 text-xs text-teal-600">
                Showing your {recentComplaints.length} most recent complaints •{' '}
                <Link to="/customer/my-complaints" className="font-medium hover:text-teal-700">View All in My Complaints</Link>
                <Link to="/customer/my-complaints" className="float-right text-teal-600 hover:text-teal-700 font-medium">Go to My Complaints →</Link>
              </div>
            </div>
          )}
        </div>

        {/* Support Section */}
        <div className="card p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between">
            <div className="flex items-center space-x-4 mb-4 md:mb-0">
              <div className="bg-teal-100 p-3 rounded-full">
                <AlertCircle size={24} className="text-teal-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Need assistance with a complaint?</h3>
                <p className="text-sm text-gray-500">Our customer support team is available Monday through Friday to answer questions about your product submissions and warranty claims.</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <a href="mailto:support@zeroq.ai" className="inline-flex items-center space-x-2 bg-white border border-gray-300 px-4 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
                <Mail size={16} /><span>Email Support</span>
              </a>
              <a href="tel:+18002430600" className="inline-flex items-center space-x-2 bg-teal-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors">
                <Phone size={16} /><span>Call 1-800-ZEROQ</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-slate-900 text-gray-400 mt-12 py-6">
        <div className="w-full px-6 lg:px-12 flex flex-col md:flex-row items-center justify-between text-xs">
          <div className="flex items-center space-x-2 mb-2 md:mb-0">
            <Zap size={14} className="text-teal-500" />
            <span className="text-white font-semibold">ZeroQ AI</span>
            <span className="text-gray-500">Operational Precision & Resolution</span>
          </div>
          <div className="flex items-center space-x-4">
            <a href="#" className="hover:text-white">Customer Support</a>
            <a href="#" className="hover:text-white">Privacy Policy</a>
            <a href="#" className="hover:text-white">Terms of Service</a>
          </div>
          <div className="mt-2 md:mt-0">© 2026 ZeroQ AI Manufacturing Inc. All rights reserved.</div>
        </div>
      </footer>
    </div>
  )
}

