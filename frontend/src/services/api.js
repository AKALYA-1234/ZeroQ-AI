import axios from 'axios'

const api = axios.create({
  baseURL: '',  // Uses Vite proxy
  timeout: 30000,
})

// Request interceptor — attach token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('zeroq_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor — handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('zeroq_token')
      localStorage.removeItem('zeroq_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
