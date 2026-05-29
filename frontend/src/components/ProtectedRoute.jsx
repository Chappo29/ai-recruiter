import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import client from '../api/client'

export default function ProtectedRoute({ children }) {
  const [state, setState] = useState('loading')

  useEffect(() => {
    client
      .get('/auth/me')
      .then(() => setState('ok'))
      .catch(() => setState('fail'))
  }, [])

  if (state === 'loading') return null
  if (state === 'fail') return <Navigate to="/login" replace />
  return children ?? <Outlet />
}
