import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'

// Auth pages
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'

// Customer pages
import CustomerLayout from './layouts/CustomerLayout'
import CustomerHome from './pages/customer/CustomerHome'
import SubmitComplaint from './pages/customer/SubmitComplaint'
import TrackComplaint from './pages/customer/TrackComplaint'
import MyComplaints from './pages/customer/MyComplaints'
import CustomerProfile from './pages/customer/CustomerProfile'
import AIQueryPrediction from './pages/customer/AIQueryPrediction'

// Admin pages
import AdminLayout from './layouts/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import ComplaintManagement from './pages/admin/ComplaintManagement'
import ComplaintAnalytics from './pages/admin/ComplaintAnalytics'
import RootCauseAnalysis from './pages/admin/RootCauseAnalysis'
import RiskAssessment from './pages/admin/RiskAssessment'
import AIPredictionCenter from './pages/admin/AIPredictionCenter'
import CAPAManagement from './pages/admin/CAPAManagement'
import AIImpactAnalytics from './pages/admin/AIImpactAnalytics'

function ProtectedCustomerRoute({ children }) {
  const { isAuthenticated, isCustomer, loading } = useAuth()
  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
    </div>
  )
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isCustomer) return <Navigate to="/admin/dashboard" replace />
  return children
}

function ProtectedAdminRoute({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth()
  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
    </div>
  )
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/customer/home" replace />
  return children
}

function RootRedirect() {
  const { isAuthenticated, isCustomer, isAdmin, loading } = useAuth()
  if (loading) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (isCustomer) return <Navigate to="/customer/home" replace />
  if (isAdmin) return <Navigate to="/admin/dashboard" replace />
  return <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route path="/customer" element={
          <ProtectedCustomerRoute><CustomerLayout /></ProtectedCustomerRoute>
        }>
          <Route index element={<Navigate to="home" replace />} />
          <Route path="home" element={<CustomerHome />} />
          <Route path="query-prediction" element={<AIQueryPrediction />} />
          <Route path="submit-complaint" element={<SubmitComplaint />} />
          <Route path="track-complaint" element={<TrackComplaint />} />
          <Route path="track-complaint/:complaintId" element={<TrackComplaint />} />
          <Route path="my-complaints" element={<MyComplaints />} />
          <Route path="profile" element={<CustomerProfile />} />
        </Route>

        <Route path="/admin" element={
          <ProtectedAdminRoute><AdminLayout /></ProtectedAdminRoute>
        }>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="complaints" element={<ComplaintManagement />} />
          <Route path="analytics" element={<ComplaintAnalytics />} />
          <Route path="root-cause-analysis" element={<RootCauseAnalysis />} />
          <Route path="risk-assessment" element={<RiskAssessment />} />
          <Route path="ai-prediction" element={<AIPredictionCenter />} />
          <Route path="capa" element={<CAPAManagement />} />
          <Route path="ai-insights" element={<AIImpactAnalytics />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
