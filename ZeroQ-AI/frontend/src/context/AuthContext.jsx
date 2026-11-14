import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('zeroq_token')
    const userData = localStorage.getItem('zeroq_user')
    if (token && userData) {
      try {
        setUser(JSON.parse(userData))
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      } catch (e) {
        localStorage.clear()
      }
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const response = await api.post('/api/auth/login', { email, password })
    const data = response.data
    localStorage.setItem('zeroq_token', data.access_token)
    localStorage.setItem('zeroq_user', JSON.stringify({
      id: data.user_id,
      email: data.email,
      role: data.role,
      full_name: data.full_name
    }))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
    setUser({ id: data.user_id, email: data.email, role: data.role, full_name: data.full_name })
    return data
  }

  const register = async (userData) => {
    const response = await api.post('/api/auth/register', userData)
    const data = response.data
    localStorage.setItem('zeroq_token', data.access_token)
    localStorage.setItem('zeroq_user', JSON.stringify({
      id: data.user_id,
      email: data.email,
      role: data.role,
      full_name: data.full_name
    }))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
    setUser({ id: data.user_id, email: data.email, role: data.role, full_name: data.full_name })
    return data
  }

  const logout = () => {
    localStorage.removeItem('zeroq_token')
    localStorage.removeItem('zeroq_user')
    delete api.defaults.headers.common['Authorization']
    setUser(null)
  }

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isCustomer: user?.role === 'customer',
    isAdmin: user?.role === 'admin' || user?.role === 'quality_manager'
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
