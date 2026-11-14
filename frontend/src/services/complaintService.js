import api from './api'

export const complaintService = {
  async submitComplaint(formData) {
    return api.post('/api/complaints/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  async getMyComplaints(params) {
    return api.get('/api/complaints/', { params })
  },
  async getComplaint(complaintId) {
    return api.get(`/api/complaints/${complaintId}`)
  },
  async getComplaintTimeline(complaintId) {
    return api.get(`/api/complaints/${complaintId}/timeline`)
  },
  async getSummary() {
    return api.get('/api/complaints/summary')
  },
  async getRecent() {
    return api.get('/api/complaints/recent')
  }
}
