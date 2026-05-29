import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import client from '../api/client'

function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
        }}
      />
      <span style={{ fontWeight: 600, fontSize: 18 }}>RecruitAI</span>
    </div>
  )
}

export default function AcceptInvite() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  if (!token) {
    return (
      <div
        style={{
          minHeight: '100vh',
          background: '#F8F9FB',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 400,
            background: '#fff',
            borderRadius: 16,
            border: '1px solid #F0F0F0',
            padding: 40,
            textAlign: 'center',
          }}
        >
          <Logo />
          <p style={{ color: '#DC2626', fontSize: 14 }}>
            Недействительная ссылка для приглашения.
          </p>
          <Link to="/login" style={{ fontSize: 13, color: '#4F46E5' }}>
            Перейти ко входу
          </Link>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div
        style={{
          minHeight: '100vh',
          background: '#F8F9FB',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 400,
            background: '#fff',
            borderRadius: 16,
            border: '1px solid #F0F0F0',
            padding: 40,
            textAlign: 'center',
          }}
        >
          <Logo />
          <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Аккаунт создан</h2>
          <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 20 }}>
            Войдите с вашим email и паролем.
          </p>
          <button
            type="button"
            onClick={() => navigate('/login')}
            style={{
              width: '100%',
              background: '#4F46E5',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: 11,
              fontWeight: 500,
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            Войти
          </button>
        </div>
      </div>
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await client.post('/team/accept-invite', {
        invitation_token: token,
        password,
      })
      setDone(true)
    } catch (err) {
      if (!err.response) {
        setError('Не удалось подключиться к серверу.')
      } else if (err.response.status === 400) {
        const detail = err.response.data?.detail
        if (typeof detail === 'string' && detail.toLowerCase().includes('expir')) {
          setError('Ссылка для приглашения истекла. Попросите администратора выслать новую.')
        } else if (typeof detail === 'string' && detail.toLowerCase().includes('invalid')) {
          setError('Недействительная ссылка для приглашения.')
        } else {
          setError(typeof detail === 'string' ? detail : 'Ошибка принятия приглашения')
        }
      } else {
        setError('Произошла ошибка. Попробуйте позже.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#F8F9FB',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 400,
          background: '#fff',
          borderRadius: 16,
          border: '1px solid #F0F0F0',
          boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
          padding: 40,
        }}
      >
        <Logo />
        <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Принять приглашение</h1>
        <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
          Придумайте пароль для вашего аккаунта
        </p>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: 20 }}>
            <span style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>
              Пароль
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              placeholder="Минимум 8 символов"
              style={{
                width: '100%',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 14,
              }}
            />
          </label>
          {error && (
            <p style={{ color: '#DC2626', fontSize: 13, marginBottom: 12 }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              background: '#4F46E5',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: 11,
              fontWeight: 500,
              fontSize: 14,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Создание аккаунта…' : 'Создать аккаунт'}
          </button>
        </form>
      </div>
    </div>
  )
}
