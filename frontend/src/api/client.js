import axios from 'axios'

// In dev, use Vite proxy (vite.config.js) with relative URLs to avoid CORS hangs.
// In dev, /api is proxied to FastAPI (see vite.config.js) — avoids clashing with SPA routes
// like /vacancies/:id and /candidates on refresh.
export const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '/api' : 'http://localhost:8000')

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
