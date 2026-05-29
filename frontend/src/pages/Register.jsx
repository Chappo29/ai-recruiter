import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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

export default function Register() {
  const navigate = useNavigate()
  const [agencyName, setAgencyName] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await client.post('/auth/register', {
        agency_name: agencyName.trim(),
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        email,
        password,
      })
      navigate('/dashboard')
    } catch (err) {
      if (!err.response) {
        setError('Не удалось подключиться к серверу. Запущен ли бэкенд?')
      } else if (err.response.status === 400) {
        const detail = err.response.data?.detail
        setError(typeof detail === 'string' ? detail : 'Не удалось зарегистрироваться')
      } else if (err.response.status === 403) {
        setError('Регистрация отключена. Обратитесь к администратору.')
      } else {
        const detail = err.response.data?.detail
        setError(
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d) => d.msg).join(', ')
              : 'Ошибка регистрации'
        )
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
        <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Создать аккаунт</h1>
        <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
          Зарегистрируйте ваше агентство в RecruitAI
        </p>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>
              Название агентства
            </span>
            <input
              type="text"
              value={agencyName}
              onChange={(e) => setAgencyName(e.target.value)}
              required
              placeholder="ООО Рекрутинг"
              style={{
                width: '100%',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 14,
              }}
            />
          </label>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <label style={{ display: 'block', flex: 1 }}>
              <span style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>Имя</span>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Иван"
                style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 8, padding: '10px 14px', fontSize: 14 }}
              />
            </label>
            <label style={{ display: 'block', flex: 1 }}>
              <span style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>Фамилия</span>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Петров"
                style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 8, padding: '10px 14px', fontSize: 14 }}
              />
            </label>
          </div>
          <label style={{ display: 'block', marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>
              Email
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                width: '100%',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 14,
              }}
            />
          </label>
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
            {loading ? 'Создание аккаунта…' : 'Зарегистрироваться'}
          </button>
        </form>
        <p style={{ textAlign: 'center', fontSize: 13, color: '#6B7280', marginTop: 20 }}>
          Уже есть аккаунт?{' '}
          <Link to="/login" style={{ color: '#4F46E5', fontWeight: 500 }}>
            Войти
          </Link>
        </p>
      </div>
    </div>
  )
}
