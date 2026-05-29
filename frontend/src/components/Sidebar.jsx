import { useEffect, useRef, useState } from 'react'
import { Bot, Briefcase, Camera, Check, LayoutDashboard, Users, X } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import client, { mediaUrl } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import NotificationBell from './NotificationBell'

const MENU = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Дашборд' },
  { path: '/vacancies', icon: Briefcase, label: 'Вакансии' },
  { path: '/candidates', icon: Users, label: 'Кандидаты' },
  { path: '/bot', icon: Bot, label: 'Telegram-бот' },
]

function initials(user) {
  if (!user) return '?'
  const f = (user.first_name || '').trim()
  const l = (user.last_name || '').trim()
  if (f && l) return (f[0] + l[0]).toUpperCase()
  if (f) return f[0].toUpperCase()
  const parts = (user.email || '').split('@')[0].split(/[._-]/)
  return parts.length >= 2
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : (parts[0][0] || '?').toUpperCase()
}

function displayName(user) {
  if (!user) return ''
  const f = (user.first_name || '').trim()
  const l = (user.last_name || '').trim()
  if (f || l) return [f, l].filter(Boolean).join(' ')
  return user.email?.split('@')[0] || ''
}

function UserAvatar({ user, size = 36, onClick, showCamera = false }) {
  const src = user?.avatar_url ? mediaUrl(user.avatar_url) : null
  return (
    <div
      onClick={onClick}
      style={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '50%',
        flexShrink: 0,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      {src ? (
        <img
          src={src}
          alt={displayName(user)}
          style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', display: 'block' }}
        />
      ) : (
        <div
          style={{
            width: size,
            height: size,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: size * 0.36,
            fontWeight: 700,
            color: '#fff',
          }}
        >
          {initials(user)}
        </div>
      )}
      {showCamera && (
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', opacity: 0, transition: 'opacity 0.15s',
        }}
          className="avatar-hover-overlay"
        >
          <Camera size={size * 0.35} color="#fff" />
        </div>
      )}
      <style>{`.avatar-hover-overlay:hover { opacity: 1 !important; }
        div:hover > .avatar-hover-overlay { opacity: 1 !important; }`}
      </style>
    </div>
  )
}

function ProfileModal({ onClose }) {
  const { user, refreshUser } = useAuth()
  const fileRef = useRef(null)
  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await client.patch('/auth/me', { first_name: firstName, last_name: lastName })
      await refreshUser()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const uploadAvatar = async (file) => {
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      await client.post('/auth/me/avatar', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      await refreshUser()
    } finally {
      setUploading(false)
    }
  }

  const logout = async () => {
    await client.post('/auth/logout')
    window.location.href = '/login'
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-start',
      }}
      onClick={onClose}
    >
      <div
        style={{
          marginLeft: 12, marginBottom: 12,
          width: 280,
          background: '#fff',
          borderRadius: 14,
          border: '1px solid #EBEBEB',
          boxShadow: '0 12px 40px rgba(0,0,0,0.14)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Avatar upload area */}
        <div style={{ background: 'linear-gradient(135deg, #EEF2FF, #F5F3FF)', padding: '20px 20px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ position: 'relative', cursor: 'pointer' }} onClick={() => fileRef.current?.click()}>
            <UserAvatar user={user} size={56} showCamera />
            {uploading && (
              <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'rgba(255,255,255,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ width: 16, height: 16, border: '2px solid #6366F1', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
              </div>
            )}
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>{displayName(user)}</div>
            <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>{user?.email}</div>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              style={{ marginTop: 6, fontSize: 11, color: '#6366F1', border: 'none', background: 'transparent', cursor: 'pointer', padding: 0, fontWeight: 500 }}
            >
              Сменить фото
            </button>
          </div>
          <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => uploadAvatar(e.target.files[0])} />
          <button type="button" onClick={onClose} style={{ marginLeft: 'auto', border: 'none', background: 'transparent', cursor: 'pointer', color: '#9CA3AF', padding: 2 }}>
            <X size={16} />
          </button>
        </div>

        {/* Name fields */}
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, display: 'block', marginBottom: 4 }}>Имя</label>
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Иван"
                style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 7, padding: '7px 10px', fontSize: 13, boxSizing: 'border-box', outline: 'none' }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500, display: 'block', marginBottom: 4 }}>Фамилия</label>
              <input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Петров"
                style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 7, padding: '7px 10px', fontSize: 13, boxSizing: 'border-box', outline: 'none' }}
              />
            </div>
          </div>

          <button
            type="button"
            onClick={save}
            disabled={saving}
            style={{
              width: '100%', padding: '8px', borderRadius: 8, border: 'none',
              background: saved ? '#F0FDF4' : '#4F46E5',
              color: saved ? '#15803D' : '#fff',
              fontSize: 13, fontWeight: 500, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              transition: 'background 0.2s',
            }}
          >
            {saved ? <><Check size={14} /> Сохранено</> : saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>

        {/* Logout */}
        <div style={{ borderTop: '1px solid #F5F5F5', padding: '10px 20px' }}>
          <button
            type="button"
            onClick={logout}
            style={{ width: '100%', padding: '8px', borderRadius: 8, border: '1px solid #FECACA', background: 'transparent', color: '#DC2626', fontSize: 13, cursor: 'pointer' }}
          >
            Выйти из аккаунта
          </button>
        </div>
      </div>
    </div>
  )
}

function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: 'linear-gradient(135deg, #6366F1, #8B5CF6)' }} />
        <span style={{ fontWeight: 600, fontSize: 15, color: '#111827' }}>RecruitAI</span>
      </div>
      <NotificationBell />
    </div>
  )
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const [profileOpen, setProfileOpen] = useState(false)

  return (
    <>
      <aside style={{ width: 220, flexShrink: 0, background: '#FFFFFF', borderRight: '1px solid #F0F0F0', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <Logo />

        <nav style={{ flex: 1, padding: '0 8px' }}>
          {MENU.map(({ path, icon: Icon, label }) => {
            const active = location.pathname === path || (path !== '/dashboard' && location.pathname.startsWith(path))
            return (
              <button
                key={path}
                type="button"
                onClick={() => navigate(path)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px', marginBottom: 4, border: 'none', borderRadius: 8,
                  background: active ? '#EEF2FF' : 'transparent',
                  color: active ? '#4F46E5' : '#6B7280',
                  fontSize: 14, fontWeight: active ? 500 : 400, textAlign: 'left',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = '#F9FAFB' }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent' }}
              >
                <Icon size={18} />
                {label}
              </button>
            )
          })}
        </nav>

        {/* User profile widget */}
        <div style={{ padding: '0 8px 12px' }}>
          <button
            type="button"
            onClick={() => setProfileOpen(true)}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 12px', border: 'none', borderRadius: 10,
              background: profileOpen ? '#EEF2FF' : 'transparent',
              cursor: 'pointer', textAlign: 'left',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { if (!profileOpen) e.currentTarget.style.background = '#F9FAFB' }}
            onMouseLeave={(e) => { if (!profileOpen) e.currentTarget.style.background = 'transparent' }}
          >
            <UserAvatar user={user} size={32} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: '#111827', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {displayName(user) || user?.email || '…'}
              </div>
              <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 1 }}>
                {user?.role === 'admin' ? 'Администратор' : 'Рекрутер'}
              </div>
            </div>
          </button>
        </div>
      </aside>

      {profileOpen && <ProfileModal onClose={() => setProfileOpen(false)} />}
    </>
  )
}

export function PageTopbar({ title, subtitle, children }) {
  return (
    <header style={{
      background: '#FFFFFF', padding: '16px 24px',
      borderBottom: '1px solid #F0F0F0',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      flexWrap: 'wrap', gap: 12,
    }}>
      <div>
        <h1 style={{ fontSize: 16, fontWeight: 600, color: '#111827', margin: 0 }}>{title}</h1>
        {subtitle && <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4, marginBottom: 0 }}>{subtitle}</p>}
      </div>
      {children}
    </header>
  )
}
