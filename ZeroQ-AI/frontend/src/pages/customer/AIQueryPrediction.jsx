import React, { useState, useEffect } from 'react'
import {
  Brain, Send, Sparkles, CheckCircle2, AlertTriangle, AlertCircle,
  HelpCircle, Clock, ArrowRight, RefreshCw, BarChart2, ShieldAlert,
  ChevronDown, ChevronUp, Layers, Check, Loader2
} from 'lucide-react'
import api from '../../services/api'

const EXAMPLE_QUERIES = [
  "Predict defect risk for Classic Biscuits in Pune facility on Night shift with temperature 135C",
  "Evaluate risk for batch BAT000004",
  "What is the complaint probability for Potato Chips produced in Chennai with high humidity of 82%?",
  "Evaluate quality for Fruit Jam with process deviation and Grade C supplier",
  "Check risk for Butter Cookies on Morning shift with line pressure 5.2 bar"
]

export default function AIQueryPrediction() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [expandedHistoryId, setExpandedHistoryId] = useState(null)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    setHistoryLoading(true)
    try {
      const res = await api.get('/api/customer/query-predictions/history')
      setHistory(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load query history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    if (e) e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await api.post('/api/customer/query-prediction', { query: query.trim() })
      if (res.data?.status === 'invalid_input') {
        setError(res.data.message)
      } else if (res.data?.status === 'error') {
        setError(res.data.message || 'Prediction failed')
      } else {
        setResult(res.data)
        fetchHistory()
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.message || 'Server error processing prediction query.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleExampleClick = (example) => {
    setQuery(example)
    setError(null)
  }

  const getRiskColor = (level) => {
    switch (level?.toLowerCase()) {
      case 'critical':
      case 'high':
        return {
          bg: 'bg-red-50',
          border: 'border-red-200',
          text: 'text-red-700',
          badge: 'bg-red-100 text-red-800 border-red-300',
          bar: 'bg-red-500'
        }
      case 'medium':
      case 'moderate':
        return {
          bg: 'bg-amber-50',
          border: 'border-amber-200',
          text: 'text-amber-700',
          badge: 'bg-amber-100 text-amber-800 border-amber-300',
          bar: 'bg-amber-500'
        }
      default:
        return {
          bg: 'bg-teal-50',
          border: 'border-teal-200',
          text: 'text-teal-700',
          badge: 'bg-teal-100 text-teal-800 border-teal-300',
          bar: 'bg-teal-500'
        }
    }
  }

  return (
    <div className="w-full px-6 lg:px-12 py-8 max-w-7xl mx-auto">
      {/* Page Title */}
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-sm shadow-teal-700/20">
            <Brain className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">AI Quality & Complaint Risk Predictor</h1>
            <p className="text-sm text-gray-500">
              Submit conversational quality queries. Our calibrated XGBoost model parses production conditions and predicts 90-day post-dispatch complaint probability.
            </p>
          </div>
        </div>
      </div>

      {/* Query Form Card */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8">
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-semibold text-gray-800 mb-2">
            Ask a Manufacturing Quality Question
          </label>
          <div className="relative mb-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Predict defect risk for Classic Biscuits in Pune facility on Night shift with temperature 135C..."
              rows={3}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent resize-none text-gray-800 placeholder-gray-400"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-3 bottom-3 inline-flex items-center space-x-2 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-300 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors shadow-sm"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <span>Predict Risk</span>
                  <Send className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>

        {/* Quick Example Queries */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2 flex items-center space-x-1">
            <Sparkles className="w-3.5 h-3.5 text-teal-600" />
            <span>Example queries to try:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((ex, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleExampleClick(ex)}
                className="text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg px-3 py-1.5 text-left transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-start space-x-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-500" />
            <div>
              <div className="font-semibold mb-0.5">Input Requirement</div>
              <div>{error}</div>
            </div>
          </div>
        )}
      </div>

      {/* Prediction Result Display */}
      {result && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden mb-8 transition-all">
          <div className="p-6 border-b border-gray-100 bg-gradient-to-r from-slate-50 to-white">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  PREDICTION RESULT • REF: {result.prediction_id}
                </span>
                <h2 className="text-xl font-bold text-gray-900 mt-0.5">
                  Pre-Dispatch Quality Risk Evaluation
                </h2>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`px-3 py-1.5 rounded-full text-xs font-bold border uppercase tracking-wider ${getRiskColor(result.risk_level).badge}`}>
                  {result.risk_level} Risk Level
                </span>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Probability KPI Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl border border-gray-100 bg-slate-50">
                <div className="text-xs font-semibold text-gray-500 uppercase">90-Day Complaint Probability</div>
                <div className="text-3xl font-extrabold text-gray-900 mt-1">
                  {(result.complaint_probability * 100).toFixed(1)}%
                </div>
                <div className="w-full bg-gray-200 h-2 rounded-full mt-3 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${getRiskColor(result.risk_level).bar}`}
                    style={{ width: `${Math.min(100, Math.max(5, result.complaint_probability * 100))}%` }}
                  />
                </div>
                <div className="text-[11px] text-gray-500 mt-2">
                  Decision Threshold: {(result.threshold * 100).toFixed(1)}%
                </div>
              </div>

              <div className="p-4 rounded-xl border border-gray-100 bg-slate-50">
                <div className="text-xs font-semibold text-gray-500 uppercase">Zero-Complaint Confidence</div>
                <div className="text-3xl font-extrabold text-teal-700 mt-1">
                  {(result.zero_complaint_probability * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-gray-500 mt-3">
                  Statistical confidence of zero customer defect escalation within 90 days.
                </div>
              </div>

              <div className="p-4 rounded-xl border border-gray-100 bg-slate-50">
                <div className="text-xs font-semibold text-gray-500 uppercase">NLP Parse Confidence</div>
                <div className="text-3xl font-extrabold text-slate-800 mt-1">
                  {(result.parse_confidence * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-500 mt-3">
                  Extracted {result.clues_extracted?.length || 0} parameter entities from your query text.
                </div>
              </div>
            </div>

            {/* Extracted Entities Chips */}
            <div>
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-teal-600" />
                <span>Extracted Query Entities</span>
              </h3>
              <div className="flex flex-wrap gap-2">
                {result.clues_extracted && result.clues_extracted.length > 0 ? (
                  result.clues_extracted.map((clue, idx) => (
                    <span key={idx} className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-medium bg-teal-50 text-teal-800 border border-teal-200">
                      <Check className="w-3 h-3 text-teal-600 mr-1.5" />
                      {clue}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-gray-400">Default operational profile applied.</span>
                )}
              </div>
            </div>

            {/* Assumed Defaults Note */}
            {result.assumed_defaults && result.assumed_defaults.length > 0 && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
                <span className="font-semibold text-slate-700">Documented Baseline Assumptions: </span>
                {result.assumed_defaults.join('; ')}.
              </div>
            )}

            {/* Key Contributing Factors */}
            {result.contributing_factors && result.contributing_factors.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center space-x-1.5">
                  <BarChart2 className="w-3.5 h-3.5 text-teal-600" />
                  <span>Primary Decision Drivers (XGBoost Feature Importance)</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {result.contributing_factors.map((factor, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-200 bg-white shadow-xs">
                      <div className="text-xs font-semibold text-gray-800 truncate" title={factor.feature_name}>
                        {factor.feature_name}
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-500 mt-1">
                        <span>Input Value: {factor.value}</span>
                        <span className="font-medium text-teal-700">Weight: {(factor.importance * 100).toFixed(2)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Plain-Language Explanation */}
            <div className={`p-4 rounded-xl border ${getRiskColor(result.risk_level).bg} ${getRiskColor(result.risk_level).border}`}>
              <div className="text-xs font-bold uppercase tracking-wider text-gray-700 mb-1">
                Quality Intelligence Summary
              </div>
              <p className={`text-sm ${getRiskColor(result.risk_level).text} leading-relaxed`}>
                {result.explanation}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Query History Section */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Your Prediction Query History</h2>
            <p className="text-xs text-gray-500 mt-0.5">Persistent audit trail of conversational quality inquiries</p>
          </div>
          <button
            onClick={fetchHistory}
            disabled={historyLoading}
            className="flex items-center space-x-1.5 text-xs text-gray-600 hover:text-gray-900 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${historyLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {historyLoading && history.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-teal-600" />
            Loading history...
          </div>
        ) : history.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <Clock className="w-10 h-10 mx-auto mb-3 text-gray-300" />
            <div className="text-sm font-medium text-gray-600 mb-1">No previous query predictions</div>
            <div className="text-xs text-gray-400">Queries you submit above will be saved here automatically.</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {history.map((item) => {
              const isExpanded = expandedHistoryId === item.prediction_id
              return (
                <div key={item.prediction_id} className="p-5 hover:bg-slate-50/50 transition-colors">
                  <div
                    className="flex flex-wrap items-center justify-between gap-3 cursor-pointer"
                    onClick={() => setExpandedHistoryId(isExpanded ? null : item.prediction_id)}
                  >
                    <div className="flex-1 min-w-[280px]">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="text-xs font-mono font-semibold text-gray-400">{item.prediction_id}</span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-500">
                          {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                        </span>
                      </div>
                      <div className="text-sm font-medium text-gray-900 leading-snug">
                        "{item.raw_query}"
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <div className="text-right">
                        <div className="text-xs font-bold text-gray-800">
                          {item.complaint_probability !== undefined && item.complaint_probability !== null
                            ? `${(item.complaint_probability * 100).toFixed(1)}% Risk`
                            : 'Evaluated'}
                        </div>
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getRiskColor(item.risk_level).badge}`}>
                          {item.risk_level || 'Low'}
                        </span>
                      </div>
                      <button className="text-gray-400 hover:text-gray-600 p-1">
                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded view */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-100 text-xs text-gray-600 space-y-2">
                      <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                        <span className="font-semibold text-slate-800">Explanation: </span>
                        {item.explanation || 'No detailed explanation saved.'}
                      </div>
                      {item.parsed_fields && Object.keys(item.parsed_fields).length > 0 && (
                        <div>
                          <span className="font-semibold text-gray-700">Parsed Parameters: </span>
                          <span className="font-mono text-gray-600">{JSON.stringify(item.parsed_fields)}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
