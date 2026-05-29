import axios from 'axios'

// In dev, /api is proxied to FastAPI (see vite.config.js)
export const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '/api' : 'http://localhost:8000')

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
  withCredentials: true,
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function mediaUrl(path) {
  if (!path) return null
  if (path.startsWith('http')) return path
  if (path.startsWith('/candidates/')) {
    return `${API_BASE_URL}${path}`
  }
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export default client
