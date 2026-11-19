import React, { useState } from 'react'
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Zap, LogOut, LayoutDashboard, FileText, BarChart2,
  GitBranch, AlertTriangle, Brain, Wrench, Search, Bell,
  ChevronRight, Home, Settings, User, Menu, X, ExternalLink, Sparkles
} from 'lucide-react'

const navItems = [
  { path: '/admin/dashboard', label: 'Executive Dashboard', icon: LayoutDashboard },
  { path: '/admin/complaints', label: 'Complaint Management', icon: FileText },
  { path: '/admin/analytics', label: 'Complaint Analytics', icon: BarChart2 },
  { path: '/admin/root-cause-analysis', label: 'AI Root Cause Analysis', icon: GitBranch },
  { path: '/admin/risk-assessment', label: 'Risk Assessment', icon: AlertTriangle },
  { path: '/admin/ai-prediction', label: 'AI Prediction Center', icon: Brain },
  { path: '/admin/ai-insights', label: 'AI Insights & Impact', icon: Sparkles },
  { path: '/admin/capa', label: 'CAPA Management', icon: Wrench },
]

const pageTitles = {
  '/admin/dashboard': { title: 'Executive Dashboard', desc: 'Monitor manufacturing quality, customer complaints, and AI-based performance across your production operations. Live synthetic complaint data.' },
  '/admin/complaints': { title: 'Complaint Management', desc: 'Review, investigate, and manage customer quality complaints across multi-site manufacturing facilities with end-to-end audit traceability.' },
  '/admin/analytics': { title: 'Complaint Analytics & Defect Epidemiology', desc: 'Manufacturing defect & complaint analytics. In-depth trend analysis, pattern detection, and data-driven quality intelligence across all product lines.' },
  '/admin/root-cause-analysis': { title: 'AI Root Cause Analysis', desc: 'Investigate recurring manufacturing quality issues, identify possible causes and review supporting evidence.' },
  '/admin/risk-assessment': { title: 'Risk Assessment', desc: 'Evaluate and monitor risk levels across products, batches and manufacturing processes.' },
  '/admin/ai-prediction': { title: 'AI Prediction Center', desc: 'Machine learning-powered predictions and forecasting for proactive complaint management.' },
  '/admin/ai-insights': { title: 'AI Insights & Impact', desc: 'Multilingual AI issue prediction performance, verified learning, and measured business impact.' },
  '/admin/capa': { title: 'CAPA Management', desc: 'Track and manage Corrective and Preventive Actions to drive continuous improvement.' },
}

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const currentPage = pageTitles[location.pathname] || { title: 'Admin', desc: '' }

  const getBreadcrumb = () => {
    const item = navItems.find(n => n.path === location.pathname)
    return item ? item.label : 'Dashboard'
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className={`${sidebarCollapsed ? 'w-16' : 'w-64'} bg-[#0f1b2d] text-white flex flex-col fixed inset-y-0 left-0 z-40 transition-all duration-300 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        {/* Logo */}
        <div className="p-4 border-b border-slate-700/50">
          <div className="flex items-center space-x-3">
            <div className="bg-teal-500 p-2 rounded-lg flex-shrink-0">
              <Zap size={20} />
            </div>
            {!sidebarCollapsed && (
              <div>
                <div className="font-bold text-sm tracking-wide">ZeroQ AI</div>
                <div className="text-[10px] text-teal-400 uppercase tracking-widest">Quality Intelligence</div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {navItems.map(item => {
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-teal-600 text-white shadow-lg shadow-teal-600/20'
                    : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                }`}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <item.icon size={18} className="flex-shrink-0" />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>

        {/* Bottom Profile */}
        {!sidebarCollapsed && (
          <div className="p-3 border-t border-slate-700/50">
            <div className="flex items-center space-x-3 px-2 py-2">
              <div className="w-9 h-9 rounded-full bg-teal-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                {user?.full_name ? user.full_name[0].toUpperCase() : 'A'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white truncate">{user?.full_name || 'Quality Manager'}</div>
                <div className="text-xs text-teal-400">Administrator</div>
              </div>
              <button
                onClick={() => { logout(); navigate('/login') }}
                className="text-gray-500 hover:text-red-400 transition-colors p-1"
                title="Sign Out"
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main content */}
      <main className={`flex-1 ${sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'} transition-all duration-300`}>
        {/* Top Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
          <div className="flex items-center justify-between px-4 lg:px-6 h-14">
            <div className="flex items-center space-x-4">
              {/* Mobile menu button */}
              <button className="lg:hidden text-gray-500 hover:text-gray-700" onClick={() => setMobileOpen(true)}>
                <Menu size={20} />
              </button>

              {/* Breadcrumb */}
              <nav className="hidden sm:flex items-center text-sm text-gray-500">
                <Home size={13} className="mr-1.5" />
                <span className="hover:text-teal-600 cursor-pointer">Executive Dashboard</span>
                <ChevronRight size={13} className="mx-1.5 text-gray-400" />
                <span className="text-gray-800 font-medium">{getBreadcrumb()}</span>
              </nav>
            </div>

            <div className="flex items-center space-x-3">
              {/* Search */}
              <div className="hidden md:flex items-center bg-gray-100 rounded-full px-3 py-1.5 w-72">
                <Search size={15} className="text-gray-400 mr-2" />
                <input
                  type="text"
                  placeholder="Search complaints, root causes, lots..."
                  className="bg-transparent text-sm text-gray-700 placeholder-gray-400 focus:outline-none w-full"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              {/* Live indicator */}
              <div className="hidden lg:flex items-center text-xs text-gray-500 space-x-1.5">
                <span className="text-gray-400">UTC {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}</span>
                <span className="flex items-center gap-1 text-emerald-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  Live
                </span>
              </div>

              {/* Notifications */}
              <button className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                <Bell size={18} />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
              </button>

              {/* Admin Profile */}
              <div className="flex items-center space-x-2 pl-3 border-l border-gray-200">
                <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-white text-xs font-bold">
                  {user?.full_name ? user.full_name[0].toUpperCase() : 'A'}
                </div>
                <div className="hidden sm:block">
                  <div className="text-xs font-medium text-gray-900">Admin Console</div>
                  <div className="text-[10px] text-gray-500">Plant Operations</div>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="p-4 lg:p-6">
          <Outlet />
        </div>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white px-6 py-3">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>© 2025 ZeroQ AI Technologies Inc. All rights reserved. • Enterprise Manufacturing Intelligence</span>
            <div className="flex items-center gap-4">
              <span className="text-emerald-600 font-medium">Demo Environment • Synthetic Quality Dataset Active</span>
            </div>
          </div>
        </footer>
      </main>
    </div>
  )
}
