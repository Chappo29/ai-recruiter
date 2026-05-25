import { Bot, Briefcase, LayoutDashboard, Users } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

const MENU = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Дашборд' },
  { path: '/vacancies', icon: Briefcase, label: 'Вакансии' },
  { path: '/candidates', icon: Users, label: 'Кандидаты' },
  { path: '/bot', icon: Bot, label: 'Telegram-бот' },
]

function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '20px 16px' }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
        }}
      />
      <span style={{ fontWeight: 600, fontSize: 15, color: '#111827' }}>RecruitAI</span>
    </div>
  )
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside
      style={{
        width: 220,
        flexShrink: 0,
        background: '#FFFFFF',
        borderRight: '1px solid #F0F0F0',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
      }}
    >
      <Logo />
      <nav style={{ flex: 1, padding: '0 8px' }}>
        {MENU.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path
          return (
            <button
              key={path}
              type="button"
              onClick={() => navigate(path)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                marginBottom: 4,
                border: 'none',
                borderRadius: 8,
                background: active ? '#EEF2FF' : 'transparent',
                color: active ? '#4F46E5' : '#6B7280',
                fontSize: 14,
                fontWeight: active ? 500 : 400,
                textAlign: 'left',
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = '#F9FAFB'
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = 'transparent'
              }}
            >
              <Icon size={18} />
              {label}
            </button>
          )
        })}
      </nav>
      <div style={{ padding: 16 }}>
        <div
          style={{
            background: '#F0FDF4',
            border: '1px solid #BBF7D0',
            borderRadius: 10,
            padding: '10px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: '#166534',
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#22C55E',
              flexShrink: 0,
            }}
          />
          @testik_bot · Активен
        </div>
      </div>
    </aside>
  )
}

export function PageTopbar({ title, subtitle, children }) {
  return (
    <header
      style={{
        background: '#FFFFFF',
        padding: '16px 24px',
        borderBottom: '1px solid #F0F0F0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      <div>
        <h1 style={{ fontSize: 16, fontWeight: 600, color: '#111827', margin: 0 }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4, marginBottom: 0 }}>
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </header>
  )
}
