import React, { useState } from 'react'
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Bell, ChevronDown, Settings, LogOut, ShieldCheck, User
} from 'lucide-react'

export default function CustomerLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)

  const navItems = [
    { path: '/customer/home', label: 'Home' },
    { path: '/customer/query-prediction', label: 'AI Risk Predictor' },
    { path: '/customer/submit-complaint', label: 'Submit Complaint' },
    { path: '/customer/track-complaint', label: 'Track Complaint' },
    { path: '/customer/my-complaints', label: 'My Complaints' },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Display values from authenticated customer profile
  const displayName = user?.full_name || (user?.email ? user.email.split('@')[0] : 'Customer')
  const displayOrg = user?.organization || 'Quality Partner'
  const initials = (displayName || 'CP')
    .split(' ')
    .filter(Boolean)
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase() || 'CP'

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800 flex flex-col font-sans">
      {/* Top Navbar matching Google Stitch UI */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="w-full px-6 lg:px-12">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/customer/home" className="flex items-center space-x-3 group">
              <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center text-white shadow-sm shadow-teal-700/20">
                <ShieldCheck className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="text-base font-bold text-slate-900 tracking-tight leading-tight">ZeroQ AI</div>
                <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Customer Quality Portal</div>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center space-x-8 h-full">
              {navItems.map(item => {
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`relative inline-flex items-center h-full text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-teal-700 font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {item.label}
                    {isActive && (
                      <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-teal-600 rounded-t-sm" />
                    )}
                  </Link>
                )
              })}
            </nav>

            {/* Right side: Notifications & Profile */}
            <div className="flex items-center space-x-4">
              {/* Notification Bell */}
              <button
                className="relative p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded-full transition-colors"
                title="Notifications"
                aria-label="Notifications"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-amber-500 rounded-full ring-2 ring-white" />
              </button>

              {/* Profile dropdown */}
              <div className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center space-x-2.5 p-1.5 pr-2.5 rounded-full hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-200"
                >
                  <div className="w-8 h-8 rounded-full bg-teal-600 text-white flex items-center justify-center text-xs font-semibold shadow-sm">
                    {initials || 'SJ'}
                  </div>
                  <div className="hidden sm:block text-left">
                    <div className="text-xs font-semibold text-slate-800 leading-tight">{displayName}</div>
                    <div className="text-[10px] text-slate-400 leading-tight">{displayOrg}</div>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                </button>

                {profileOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-100 py-1.5 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <p className="text-sm font-semibold text-slate-900">{displayName}</p>
                      <p className="text-xs text-slate-500 truncate">{user?.email || 'customer@zeroq.ai'}</p>
                      <p className="text-[11px] text-teal-600 mt-0.5 font-medium">{displayOrg}</p>
                    </div>

                    <Link
                      to="/customer/profile"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center space-x-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <Settings className="w-4 h-4 text-slate-400" />
                      <span>Account Settings</span>
                    </Link>

                    <button
                      onClick={handleLogout}
                      className="flex items-center space-x-2.5 w-full text-left px-4 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors"
                    >
                      <LogOut className="w-4 h-4 text-rose-500" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Mobile Navigation bar */}
        <div className="md:hidden border-t border-slate-100 flex overflow-x-auto px-4 py-2 space-x-4 bg-slate-50/50">
          {navItems.map(item => {
            const isActive = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`text-xs whitespace-nowrap py-1 px-2 rounded-md ${
                  isActive ? 'bg-teal-50 text-teal-700 font-semibold' : 'text-slate-600'
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        <Outlet />
      </main>
    </div>
  )
}
