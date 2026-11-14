import React, { useState, useEffect } from 'react'
import {
  User, Mail, Phone, Building2, Briefcase, Globe, MapPin, Home,
  ChevronRight, Shield, Lock, Eye, EyeOff, Check, X, Bell, LogOut,
  Trash2, Save, RotateCcw, KeyRound, Clock, Calendar, Languages,
  BadgeCheck, AlertCircle, Fingerprint
} from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../context/AuthContext'

export default function CustomerProfile() {
  const { user } = useAuth()

  const [profile, setProfile] = useState({
    fullName: '',
    email: '',
    contactNumber: '',
    company: '',
    jobTitle: '',
    country: '',
    city: '',
    address: ''
  })

  const [preferences, setPreferences] = useState({
    language: 'English',
    timezone: 'UTC+05:30 (IST)',
    dateFormat: 'DD/MM/YYYY'
  })

  const [passwords, setPasswords] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })

  const [notifications, setNotifications] = useState({
    complaintSubmission: true,
    statusUpdates: true,
    investigationUpdates: true,
    resolutionNotifications: true,
    emailNotifications: true,
    smsAlerts: false
  })

  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)
  const [savingNotifications, setSavingNotifications] = useState(false)

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      const res = await api.get('/api/customer/profile')
      if (res.data) {
        setProfile({
          fullName: res.data.fullName || '',
          email: res.data.email || '',
          contactNumber: res.data.contactNumber || '',
          company: res.data.company || '',
          jobTitle: res.data.jobTitle || '',
          country: res.data.country || '',
          city: res.data.city || '',
          address: res.data.address || ''
        })
        if (res.data.preferences) setPreferences(res.data.preferences)
        if (res.data.notifications) setNotifications(res.data.notifications)
      }
    } catch (err) {
      console.error('Failed to fetch profile:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      await api.put('/api/customer/profile', { ...profile, preferences })
    } catch (err) {
      console.error('Failed to update profile:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (passwords.newPassword !== passwords.confirmPassword) return
    setSavingPassword(true)
    try {
      await api.put('/api/customer/change-password', {
        currentPassword: passwords.currentPassword,
        newPassword: passwords.newPassword
      })
      setPasswords({ currentPassword: '', newPassword: '', confirmPassword: '' })
    } catch (err) {
      console.error('Failed to change password:', err)
    } finally {
      setSavingPassword(false)
    }
  }

  const handleSaveNotifications = async () => {
    setSavingNotifications(true)
    try {
      await api.put('/api/customer/notification-preferences', notifications)
    } catch (err) {
      console.error('Failed to update notification preferences:', err)
    } finally {
      setSavingNotifications(false)
    }
  }

  const passwordChecks = {
    minLength: passwords.newPassword.length >= 8,
    uppercase: /[A-Z]/.test(passwords.newPassword),
    number: /[0-9]/.test(passwords.newPassword),
    special: /[!@#$%^&*(),.?":{}|<>]/.test(passwords.newPassword)
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
      </div>
    )
  }

  return (
    <div className="w-full px-6 lg:px-12 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-gray-500 mb-6">
        <Home size={14} className="mr-1" />
        <span className="hover:text-teal-600 cursor-pointer">Home</span>
        <ChevronRight size={14} className="mx-2" />
        <span className="text-gray-900 font-medium">My Profile</span>
      </nav>

      {/* Page Title */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
        <p className="text-gray-500 mt-1">Manage your personal information, security settings, and notification preferences</p>
      </div>

      {/* Profile Header Card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-5">
            <div className="w-20 h-20 rounded-2xl bg-teal-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
              {getInitials(profile.fullName || user?.name)}
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h2 className="text-xl font-bold text-gray-900">{profile.fullName || user?.name || 'User'}</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal-100 text-teal-700">Customer</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Active Customer
                </span>
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                <span className="flex items-center gap-1.5">
                  <Mail size={14} />
                  {profile.email || user?.email}
                </span>
                {profile.company && (
                  <span className="flex items-center gap-1.5">
                    <Building2 size={14} />
                    {profile.company}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-400 mt-2">
                <span className="flex items-center gap-1.5">
                  <Calendar size={12} />
                  Member since January 2025
                </span>
                <span className="flex items-center gap-1.5">
                  <KeyRound size={12} />
                  Client Key: AD-88402
                </span>
              </div>
            </div>
          </div>
          <button className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2">
            <User size={14} />
            Edit Profile
          </button>
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT COLUMN */}
        <div className="space-y-6">
          {/* Personal Information */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Personal Information</h3>
            <p className="text-sm text-gray-500 mb-5">Update your personal details and contact information</p>

            <div className="space-y-4">
              {/* Full Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
                <div className="relative">
                  <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={profile.fullName}
                    onChange={e => setProfile({ ...profile, fullName: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your full name"
                  />
                </div>
              </div>

              {/* Email Address */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="email"
                    value={profile.email}
                    onChange={e => setProfile({ ...profile, email: e.target.value })}
                    className="w-full pl-10 pr-24 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your email"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 flex items-center gap-1">
                    <BadgeCheck size={12} />
                    Verified
                  </span>
                </div>
              </div>

              {/* Contact Number */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Contact Number</label>
                <div className="relative">
                  <Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="tel"
                    value={profile.contactNumber}
                    onChange={e => setProfile({ ...profile, contactNumber: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your contact number"
                  />
                </div>
              </div>

              {/* Company/Organization */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Company / Organization</label>
                <div className="relative">
                  <Building2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={profile.company}
                    onChange={e => setProfile({ ...profile, company: e.target.value })}
                    className="w-full pl-10 pr-24 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your organization"
                  />
                  {profile.company && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 flex items-center gap-1">
                      <Building2 size={12} />
                      Linked
                    </span>
                  )}
                </div>
              </div>

              {/* Job Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Job Title <span className="text-gray-400 font-normal">(Optional)</span>
                </label>
                <div className="relative">
                  <Briefcase size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={profile.jobTitle}
                    onChange={e => setProfile({ ...profile, jobTitle: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your job title"
                  />
                </div>
              </div>

              {/* Country */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Country</label>
                <div className="relative">
                  <Globe size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <select
                    value={profile.country}
                    onChange={e => setProfile({ ...profile, country: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent appearance-none bg-white"
                  >
                    <option value="">Select Country</option>
                    <option value="India">India</option>
                    <option value="United States">United States</option>
                    <option value="United Kingdom">United Kingdom</option>
                    <option value="Canada">Canada</option>
                    <option value="Australia">Australia</option>
                    <option value="Germany">Germany</option>
                    <option value="France">France</option>
                    <option value="Japan">Japan</option>
                    <option value="Singapore">Singapore</option>
                    <option value="UAE">UAE</option>
                  </select>
                </div>
              </div>

              {/* City */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">City</label>
                <div className="relative">
                  <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={profile.city}
                    onChange={e => setProfile({ ...profile, city: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter your city"
                  />
                </div>
              </div>

              {/* Address */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Address <span className="text-gray-400 font-normal">(Optional)</span>
                </label>
                <textarea
                  value={profile.address}
                  onChange={e => setProfile({ ...profile, address: e.target.value })}
                  rows={3}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent resize-none"
                  placeholder="Enter your full address"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
                <button
                  onClick={handleSaveProfile}
                  disabled={saving}
                  className="px-5 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  <Save size={14} />
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>

          {/* Account Preferences */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Account Preferences</h3>
            <p className="text-sm text-gray-500 mb-5">Customize your language, timezone, and display settings</p>

            <div className="space-y-4">
              {/* Preferred Language */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Preferred Language</label>
                <div className="relative">
                  <Languages size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <select
                    value={preferences.language}
                    onChange={e => setPreferences({ ...preferences, language: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent appearance-none bg-white"
                  >
                    <option value="English">English</option>
                    <option value="Hindi">Hindi</option>
                    <option value="Tamil">Tamil</option>
                    <option value="Spanish">Spanish</option>
                    <option value="French">French</option>
                    <option value="German">German</option>
                  </select>
                </div>
              </div>

              {/* Time Zone */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Time Zone</label>
                <div className="relative">
                  <Clock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <select
                    value={preferences.timezone}
                    onChange={e => setPreferences({ ...preferences, timezone: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent appearance-none bg-white"
                  >
                    <option value="UTC+05:30 (IST)">UTC+05:30 (IST) - India Standard Time</option>
                    <option value="UTC+00:00 (GMT)">UTC+00:00 (GMT) - Greenwich Mean Time</option>
                    <option value="UTC-05:00 (EST)">UTC-05:00 (EST) - Eastern Standard Time</option>
                    <option value="UTC-08:00 (PST)">UTC-08:00 (PST) - Pacific Standard Time</option>
                    <option value="UTC+08:00 (SGT)">UTC+08:00 (SGT) - Singapore Time</option>
                    <option value="UTC+09:00 (JST)">UTC+09:00 (JST) - Japan Standard Time</option>
                  </select>
                </div>
              </div>

              {/* Date Format */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Date Format</label>
                <div className="relative">
                  <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <select
                    value={preferences.dateFormat}
                    onChange={e => setPreferences({ ...preferences, dateFormat: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent appearance-none bg-white"
                  >
                    <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                    <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                    <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                    <option value="DD-MMM-YYYY">DD-MMM-YYYY</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-6">
          {/* Account Security */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Account Security</h3>
            <p className="text-sm text-gray-500 mb-5">Keep your account safe by updating your password regularly</p>

            <div className="space-y-4">
              {/* Current Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Current Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type={showCurrentPassword ? 'text' : 'password'}
                    value={passwords.currentPassword}
                    onChange={e => setPasswords({ ...passwords, currentPassword: e.target.value })}
                    className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter current password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showCurrentPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    value={passwords.newPassword}
                    onChange={e => setPasswords({ ...passwords, newPassword: e.target.value })}
                    className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Enter new password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Confirm New Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={passwords.confirmPassword}
                    onChange={e => setPasswords({ ...passwords, confirmPassword: e.target.value })}
                    className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    placeholder="Confirm new password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Password Requirements */}
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs font-semibold text-gray-700 mb-2">Password Requirements:</p>
                <div className="space-y-1.5">
                  {[
                    { key: 'minLength', label: 'Minimum 8 characters' },
                    { key: 'uppercase', label: 'At least 1 uppercase letter' },
                    { key: 'number', label: 'At least 1 number or special character' },
                    { key: 'special', label: 'At least 1 special symbol (!@#$%^&*)' }
                  ].map(req => (
                    <div key={req.key} className="flex items-center gap-2">
                      {passwordChecks[req.key] ? (
                        <Check size={14} className="text-emerald-500" />
                      ) : (
                        <X size={14} className="text-gray-300" />
                      )}
                      <span className={`text-xs ${passwordChecks[req.key] ? 'text-emerald-600' : 'text-gray-500'}`}>
                        {req.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleChangePassword}
                disabled={savingPassword || !passwordChecks.minLength || !passwordChecks.uppercase || !passwordChecks.number || !passwordChecks.special}
                className="w-full px-5 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Shield size={14} />
                {savingPassword ? 'Updating...' : 'Update Password'}
              </button>

              {/* Authentication Safeguards */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Fingerprint size={16} className="text-teal-600" />
                  Authentication Safeguards
                </h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <BadgeCheck size={16} className="text-emerald-500" />
                      <span className="text-sm text-gray-700">Email identity verified</span>
                    </div>
                    <span className="text-xs text-emerald-600 font-medium">Confirmed</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <Clock size={16} className="text-gray-400" />
                      <span className="text-sm text-gray-700">Last Successful Login</span>
                    </div>
                    <span className="text-xs text-gray-500">Today, 10:30 AM</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Account Information */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Information</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-500">Activity Status</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Active Customer
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-500">Member Since</span>
                <span className="text-sm text-gray-900 font-medium">January 2025</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-500">Customer ID</span>
                <span className="text-sm text-gray-900 font-mono">AD-88402</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-500">Account Type</span>
                <span className="text-sm text-gray-900 font-medium">Customer</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Notification Preferences - Full Width */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-1">Notification Preferences</h3>
        <p className="text-sm text-gray-500 mb-5">Choose which notifications you'd like to receive</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { key: 'complaintSubmission', label: 'Complaint Submission Confirmation', desc: 'Get notified when your complaint is submitted' },
            { key: 'statusUpdates', label: 'Complaint Status Updates', desc: 'Receive updates on complaint status changes' },
            { key: 'investigationUpdates', label: 'Investigation Updates', desc: 'Get notified about investigation progress' },
            { key: 'resolutionNotifications', label: 'Complaint Resolution Notifications', desc: 'Receive alerts when complaints are resolved' },
            { key: 'emailNotifications', label: 'Email Notifications', desc: 'Receive all notifications via email' },
            { key: 'smsAlerts', label: 'SMS Alerts', desc: 'Receive urgent alerts via SMS' }
          ].map(item => (
            <div key={item.key} className="flex items-start justify-between p-4 bg-gray-50 rounded-lg">
              <div className="pr-4">
                <p className="text-sm font-medium text-gray-900">{item.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
              </div>
              <button
                onClick={() => setNotifications({ ...notifications, [item.key]: !notifications[item.key] })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0 ${
                  notifications[item.key] ? 'bg-teal-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm ${
                    notifications[item.key] ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>

        <div className="flex justify-end mt-5">
          <button
            onClick={handleSaveNotifications}
            disabled={savingNotifications}
            className="px-5 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Bell size={14} />
            {savingNotifications ? 'Saving...' : 'Save Preferences'}
          </button>
        </div>
      </div>

      {/* Account Actions & Security Session */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Actions & Security Session</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <button className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2">
            <LogOut size={16} />
            Sign Out of All Sessions
          </button>
          <button className="px-4 py-2.5 border border-red-200 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2">
            <Trash2 size={16} />
            Request Account Deletion
          </button>
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div className="flex items-center justify-end gap-3 mt-6 pb-8">
        <button className="px-5 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2">
          <RotateCcw size={14} />
          Discard Changes
        </button>
        <button
          onClick={handleSaveProfile}
          disabled={saving}
          className="px-6 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-50 flex items-center gap-2 shadow-sm"
        >
          <Save size={14} />
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}

