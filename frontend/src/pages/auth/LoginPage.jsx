import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { Eye, EyeOff, AlertCircle, Loader2, Zap } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(email, password)
      if (data.role === 'customer') navigate('/customer/home')
      else navigate('/admin/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-teal-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center bg-teal-500 w-16 h-16 rounded-2xl mb-4 shadow-lg shadow-teal-500/30">
            <Zap size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">ZeroQ AI</h1>
          <p className="text-teal-300 mt-1">Manufacturing Quality Intelligence Platform</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Welcome back</h2>
          <p className="text-gray-500 text-sm mb-6">Sign in to your account to continue</p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2 text-red-600 text-sm">
              <AlertCircle size={16} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                className="input-field" placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input type={showPassword ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)} required
                  className="input-field pr-10" placeholder="••••••••" />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-gray-400 hover:text-gray-600">
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full btn-primary flex items-center justify-center space-x-2">
              {loading ? <><Loader2 size={18} className="animate-spin" /><span>Signing in...</span></> : <span>Sign In</span>}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Don't have an account?{' '}
              <Link to="/register" className="text-teal-600 hover:text-teal-700 font-medium">Create one</Link>
            </p>
          </div>

          <div className="mt-6 p-4 bg-teal-50 rounded-lg border border-teal-100">
            <p className="text-xs font-semibold text-teal-700 mb-2">Demo Credentials</p>
            <div className="text-xs text-teal-600 space-y-1">
              <p><span className="font-medium">Customer:</span> demo@customer.com / DemoCustomer2024!</p>
              <p><span className="font-medium">Admin:</span> admin@zeroq.com / AdminZeroQ2024!</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

