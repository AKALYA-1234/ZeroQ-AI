import React, { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'
import {
  Brain, AlertTriangle, Info, Download, RefreshCw, CheckCircle,
  Clock, Shield, Eye, Activity, Zap, Package, MapPin,
  Calendar, Hash, ChevronDown, Target, TrendingUp, AlertCircle
} from 'lucide-react'
import api from '../../services/api'

function Badge({ children, className }) { return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${className}`}>{children}</span> }
const RISK_BG = { critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700', medium: 'bg-amber-100 text-amber-700', low: 'bg-green-100 text-green-700' }
const RISK_COLORS = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }

export default function AIPredictionCenter() {
  const [modelStatus, setModelStatus] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [predicting, setPredicting] = useState(false)
  const [predictionResult, setPredictionResult] = useState(null)
  const [products, setProducts] = useState([])
  const [predictionMode, setPredictionMode] = useState('batch')
  const [inputForm, setInputForm] = useState({
    product: '', batch: '', facility: '', category: '', severity: '',
    description: '', horizon: '30'
  })

  useEffect(() => { fetchData() }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statusRes, infoRes, histRes, prodRes] = await Promise.all([
        api.get('/api/predictions/status'),
        api.get('/api/admin/predictions/model-info').catch(() => ({ data: {} })),
        api.get('/api/admin/predictions/history').catch(() => ({ data: { items: [] } })),
        api.get('/api/admin/filters/products').catch(() => ({ data: [] }))
      ])
      setModelStatus(statusRes.data)
      setModelInfo(infoRes.data)
      setHistory(histRes.data?.items || [])
      const prods = Array.isArray(prodRes.data) ? prodRes.data : (Array.isArray(prodRes.data?.products) ? prodRes.data.products : [])
      setProducts(prods)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const runPrediction = async () => {
    setPredicting(true)
    try {
      const res = await api.post('/api/admin/predictions/predict', {
        product_id: inputForm.product ? parseInt(inputForm.product) : null,
        category: inputForm.category || null,
        severity: inputForm.severity || null,
        description: inputForm.description || null,
        batch_id: inputForm.batch || null,
        facility: inputForm.facility || null,
      })
      setPredictionResult(res.data)
      fetchData() // refresh history
    } catch (err) {
      console.error(err)
      setPredictionResult({ status: 'error', message: 'Prediction request failed. Please check backend connection.' })
    } finally { setPredicting(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto"></div>
    </div>
  )

  const isModelAvailable = modelStatus?.status === 'active' || modelInfo?.model_deployed
  const meta = modelInfo?.model_metadata || {}
  const metrics = modelInfo?.metrics || {}
  const featureImportance = modelInfo?.feature_importance || []

  return (
    <div className="max-w-full">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Prediction Center</h1>
          <p className="text-sm text-gray-500 mt-1">XGBoost-powered complaint risk prediction for proactive quality management.</p>
        </div>
        <div className="flex items-center gap-2 mt-3 lg:mt-0">
          <button onClick={fetchData} className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><RefreshCw size={14} /> Refresh</button>
          <button className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={14} /> Export</button>
        </div>
      </div>

      {/* Model Status Banner */}
      {isModelAvailable ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <CheckCircle size={20} className="text-green-600 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-green-800">XGBoost Model Active — {meta.model_version || 'v1.0'}</h3>
            <p className="text-xs text-green-700 mt-1">
              {meta.algorithm || 'XGBoost Classifier'} loaded with {meta.n_features?.toLocaleString() || '10,038'} features.
              Best AUC: {meta.training_metrics?.best_auc || 'N/A'} | Best iteration: {meta.training_metrics?.best_iteration || 'N/A'} of {meta.n_estimators || 'N/A'} rounds.
              File: {meta.file_size_kb ? `${meta.file_size_kb} KB` : 'loaded'}.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertTriangle size={20} className="text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-amber-800">Model Not Available</h3>
            <p className="text-xs text-amber-700 mt-1">{modelStatus?.model_error || 'Place trained model file (final_xgboost_model.joblib) in the project root and restart the backend.'}</p>
          </div>
        </div>
      )}

      {/* Model Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Algorithm</div>
          <div className="text-sm font-bold text-gray-900 mt-1">{meta.algorithm || 'XGBoost'}</div>
          <Badge className={isModelAvailable ? 'bg-green-100 text-green-700 mt-1' : 'bg-amber-100 text-amber-700 mt-1'}>{isModelAvailable ? 'Active' : 'Unavailable'}</Badge>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Model Version</div>
          <div className="text-sm font-bold text-gray-900 mt-1">{meta.model_version || modelInfo?.current_version || 'N/A'}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">binary:logistic</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Features</div>
          <div className="text-lg font-bold text-teal-700 mt-1">{meta.n_features?.toLocaleString() || 'N/A'}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">input dimensions</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Best AUC</div>
          <div className="text-lg font-bold text-gray-900 mt-1">{meta.training_metrics?.best_auc || 'N/A'}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">validation metric</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Best Iteration</div>
          <div className="text-lg font-bold text-gray-900 mt-1">{meta.training_metrics?.best_iteration || 'N/A'}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">of {meta.n_estimators || 'N/A'} rounds</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">Total Predictions</div>
          <div className="text-lg font-bold text-teal-700 mt-1">{modelInfo?.total_predictions || 0}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">lifetime</div>
        </div>
      </div>

      {/* Prediction Modes */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-3">Prediction Modes</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { id: 'batch', label: 'Batch Complaint Risk', icon: Package, available: true },
            { id: 'product', label: 'Product Complaint Risk', icon: Target, available: true },
            { id: 'future', label: 'Future Risk Probability', icon: TrendingUp, available: true },
            { id: 'category', label: 'Category Prediction', icon: Brain, available: false },
            { id: 'volume', label: 'Volume Forecast', icon: Activity, available: false }
          ].map(mode => (
            <button key={mode.id} onClick={() => mode.available && setPredictionMode(mode.id)} className={`p-3 rounded-lg border-2 text-left transition-all ${
              predictionMode === mode.id ? 'border-teal-500 bg-teal-50' : mode.available ? 'border-gray-200 hover:border-gray-300' : 'border-gray-100 opacity-50'
            }`}>
              <mode.icon size={16} className={predictionMode === mode.id ? 'text-teal-600' : 'text-gray-400'} />
              <div className="text-xs font-medium text-gray-800 mt-1">{mode.label}</div>
              <Badge className={mode.available ? 'bg-green-100 text-green-600 mt-1' : 'bg-gray-100 text-gray-500 mt-1'}>{mode.available ? 'Available' : 'Coming Soon'}</Badge>
            </button>
          ))}
        </div>
      </div>

      {/* Prediction Form + Result */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Input Form */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Prediction Input</h3>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Product</label>
              <select className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" value={inputForm.product} onChange={e => setInputForm({...inputForm, product: e.target.value})}>
                <option value="">Select Product</option>
                {products.map(p => <option key={p.id || p} value={p.id || p}>{p.name || p}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Category</label>
                <select className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" value={inputForm.category} onChange={e => setInputForm({...inputForm, category: e.target.value})}>
                  <option value="">Select Category</option>
                  {['Product Defect', 'Packaging Issue', 'Performance Issue', 'Material Quality Issue', 'Contamination', 'Labeling Error', 'Dimensional Defect'].map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Severity</label>
                <select className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" value={inputForm.severity} onChange={e => setInputForm({...inputForm, severity: e.target.value})}>
                  <option value="">Select Severity</option>
                  {['low', 'medium', 'high', 'critical'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Batch ID</label>
              <input type="text" placeholder="e.g., BAT000001" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={inputForm.batch} onChange={e => setInputForm({...inputForm, batch: e.target.value})} />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Complaint Description</label>
              <textarea rows={3} placeholder="Describe the complaint or quality issue..." className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none" value={inputForm.description} onChange={e => setInputForm({...inputForm, description: e.target.value})} />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-500 uppercase mb-1 block">Facility</label>
              <input type="text" placeholder="e.g., Pune Manufacturing Unit" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" value={inputForm.facility} onChange={e => setInputForm({...inputForm, facility: e.target.value})} />
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={runPrediction} disabled={predicting || !isModelAvailable} className="flex-1 px-4 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 flex items-center justify-center gap-1.5">
                <Brain size={14} /> {predicting ? 'Running XGBoost...' : 'Run Prediction'}
              </button>
              <button onClick={() => { setInputForm({ product: '', batch: '', facility: '', category: '', severity: '', description: '', horizon: '30' }); setPredictionResult(null) }} className="px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">Clear</button>
            </div>
          </div>
        </div>

        {/* Result */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Prediction Result</h3>
          {predictionResult ? (
            predictionResult.status === 'error' ? (
              <div className="text-center py-8">
                <AlertCircle size={32} className="text-red-500 mx-auto mb-3" />
                <h4 className="text-sm font-bold text-red-700">Prediction Failed</h4>
                <p className="text-xs text-gray-500 mt-1">{predictionResult.message}</p>
              </div>
            ) : predictionResult.status === 'Model Unavailable' ? (
              <div className="text-center py-8">
                <AlertTriangle size={32} className="text-amber-500 mx-auto mb-3" />
                <h4 className="text-sm font-bold text-amber-800">Model Unavailable</h4>
                <p className="text-xs text-gray-500 mt-1">{predictionResult.prediction?.note}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Risk Level Gauge */}
                <div className={`rounded-xl p-5 text-center ${
                  predictionResult.prediction?.predicted_severity === 'critical' ? 'bg-red-50 border border-red-200' :
                  predictionResult.prediction?.predicted_severity === 'high' ? 'bg-orange-50 border border-orange-200' :
                  predictionResult.prediction?.predicted_severity === 'medium' ? 'bg-amber-50 border border-amber-200' :
                  'bg-green-50 border border-green-200'
                }`}>
                  <div className="text-[10px] text-gray-500 uppercase mb-2">XGBoost Risk Assessment</div>
                  <div className="text-3xl font-bold mb-1" style={{color: RISK_COLORS[predictionResult.prediction?.predicted_severity] || '#6b7280'}}>
                    {predictionResult.prediction?.risk_label || 'Unknown'}
                  </div>
                  <div className="flex items-center justify-center gap-4 mt-2">
                    <div>
                      <div className="text-[10px] text-gray-500">Risk Probability</div>
                      <div className="text-lg font-bold font-mono text-gray-800">{((predictionResult.prediction?.risk_probability || 0) * 100).toFixed(1)}%</div>
                    </div>
                    <div className="h-8 w-px bg-gray-200"></div>
                    <div>
                      <div className="text-[10px] text-gray-500">Confidence</div>
                      <div className="text-lg font-bold font-mono text-gray-800">{((predictionResult.prediction?.confidence || 0) * 100).toFixed(1)}%</div>
                    </div>
                    <div className="h-8 w-px bg-gray-200"></div>
                    <div>
                      <div className="text-[10px] text-gray-500">Class</div>
                      <div className="text-lg font-bold font-mono text-gray-800">{predictionResult.prediction?.risk_class}</div>
                    </div>
                  </div>
                  {/* Risk probability bar */}
                  <div className="mt-3 bg-gray-200 rounded-full h-2.5 w-full max-w-xs mx-auto overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500" style={{
                      width: `${(predictionResult.prediction?.risk_probability || 0) * 100}%`,
                      backgroundColor: RISK_COLORS[predictionResult.prediction?.predicted_severity] || '#6b7280'
                    }}></div>
                  </div>
                  <div className="flex justify-between text-[9px] text-gray-400 max-w-xs mx-auto mt-1">
                    <span>0% Low</span><span>50%</span><span>100% Critical</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-[10px] text-gray-500">Predicted Severity</div>
                    <Badge className={`mt-1 ${RISK_BG[predictionResult.prediction?.predicted_severity] || 'bg-gray-100 text-gray-600'}`}>
                      {predictionResult.prediction?.predicted_severity?.toUpperCase() || 'N/A'}
                    </Badge>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-[10px] text-gray-500">Predicted Category</div>
                    <div className="text-xs font-medium text-gray-800 mt-1">{predictionResult.prediction?.predicted_category || 'N/A'}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-[10px] text-gray-500">Model Version</div>
                    <div className="text-xs font-medium text-gray-800 mt-1">{predictionResult.prediction?.model_version || 'N/A'}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-[10px] text-gray-500">Prediction ID</div>
                    <div className="text-xs font-mono text-teal-700 mt-1">{predictionResult.prediction_id || 'N/A'}</div>
                  </div>
                </div>

                {/* Feature Summary */}
                {predictionResult.prediction?.feature_summary && (
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Feature Engineering Summary</div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div><span className="text-gray-400">Total:</span> <span className="font-mono text-gray-700">{predictionResult.prediction.feature_summary.total_features?.toLocaleString()}</span></div>
                      <div><span className="text-gray-400">Active:</span> <span className="font-mono text-gray-700">{predictionResult.prediction.feature_summary.active_features}</span></div>
                      <div><span className="text-gray-400">Product:</span> <span className="text-gray-700">{predictionResult.prediction.feature_summary.product || '—'}</span></div>
                    </div>
                  </div>
                )}

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <p className="text-[10px] text-amber-800 flex items-start gap-1.5"><Info size={12} className="mt-0.5 flex-shrink-0" /> This prediction is based on statistical patterns. Model associations are not verified root causes. Always validate findings with domain expertise.</p>
                </div>
              </div>
            )
          ) : (
            <div className="text-center py-12 text-gray-400">
              <Brain size={40} className="mx-auto mb-3 text-gray-300" />
              <p className="text-sm font-medium">{isModelAvailable ? 'Configure inputs and run a prediction' : 'Model not available'}</p>
              <p className="text-xs mt-1">{isModelAvailable ? 'Select product, category, severity and add a description' : 'Ensure final_xgboost_model.joblib is in the project root'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Model Hyperparameters & Feature Importance side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Hyperparameters */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Model Hyperparameters</h3>
          {meta.hyperparameters ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(meta.hyperparameters).map(([key, value]) => (
                <div key={key} className="bg-gray-50 rounded-lg p-2.5">
                  <div className="text-[10px] text-gray-500 uppercase">{key.replace(/_/g, ' ')}</div>
                  <div className="text-xs font-mono font-medium text-gray-800 mt-0.5">{value ?? 'N/A'}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <Shield size={24} className="mx-auto mb-2" />
              <p className="text-sm">Hyperparameters available after model loading</p>
            </div>
          )}
        </div>

        {/* Feature Importance Chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Top Feature Importances</h3>
          {featureImportance.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={featureImportance.slice(0, 10)} layout="vertical" margin={{ left: 120, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="feature_label" tick={{ fontSize: 9 }} width={110} />
                <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v) => [v.toFixed(6), 'Importance']} />
                <Bar dataKey="importance" fill="#0d9488" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <Activity size={24} className="mx-auto mb-2" />
              <p className="text-sm">Feature importance available after model loading</p>
            </div>
          )}
        </div>
      </div>

      {/* Model Information */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-4">Model Information</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Algorithm', value: meta.algorithm || 'Not loaded' },
            { label: 'Objective', value: meta.objective || 'binary:logistic' },
            { label: 'Task', value: meta.task || 'Risk Classification' },
            { label: 'Feature Count', value: meta.n_features?.toLocaleString() || 'N/A' },
            { label: 'Classes', value: meta.classes ? meta.classes.join(', ') : 'N/A' },
            { label: 'Class Labels', value: meta.class_labels ? Object.values(meta.class_labels).join(' / ') : 'N/A' },
            { label: 'File Size', value: meta.file_size_kb ? `${meta.file_size_kb} KB` : 'N/A' },
            { label: 'Model Version', value: meta.model_version || 'N/A' }
          ].map(item => (
            <div key={item.label} className="bg-gray-50 rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase">{item.label}</div>
              <div className="text-xs font-medium text-gray-800 mt-0.5">{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Prediction History */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h3 className="text-sm font-bold text-gray-900 mb-4">Prediction History</h3>
        {history.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">ID</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Product</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Risk</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Confidence</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Date</th>
                  <th className="text-left py-2 px-3 text-[10px] font-semibold text-gray-500 uppercase">Model</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 font-mono text-teal-700">{h.prediction_id}</td>
                    <td className="py-2 px-3 text-gray-700">{h.input_features?.product_name || h.input_features?.product || 'N/A'}</td>
                    <td className="py-2 px-3">
                      <Badge className={RISK_BG[h.prediction_result?.predicted_severity] || 'bg-gray-100 text-gray-600'}>
                        {h.prediction_result?.risk_label || h.prediction_result?.predicted_severity || 'N/A'}
                      </Badge>
                    </td>
                    <td className="py-2 px-3 font-mono text-gray-700">{h.confidence_score ? `${(parseFloat(h.confidence_score) * 100).toFixed(1)}%` : 'N/A'}</td>
                    <td className="py-2 px-3 text-gray-500">{h.created_at ? new Date(h.created_at).toLocaleDateString() : '—'}</td>
                    <td className="py-2 px-3 text-gray-500">{h.model_version || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <Clock size={24} className="mx-auto mb-2" />
            <p className="text-sm">No predictions have been made yet</p>
            <p className="text-xs mt-1">Run a prediction above to see history</p>
          </div>
        )}
      </div>

      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-[10px] text-gray-500 flex items-center gap-1.5">
          <Info size={12} className="text-slate-400" />
          Predictions use the trained XGBoost model (binary:logistic, 10,038 features, AUC {meta.training_metrics?.best_auc || '0.5469'}). Results are AI-generated risk estimates, not verified outcomes. Always validate with domain expertise.
        </p>
      </div>
    </div>
  )
}
