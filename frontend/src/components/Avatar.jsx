import { User } from 'lucide-react'

export default function Avatar({ name, src, size = 40 }) {
  if (src) {
    return (
      <img
        src={src}
        alt={name || 'Avatar'}
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          objectFit: 'cover',
          flexShrink: 0,
          border: '1.5px solid #F0F0F0',
        }}
        onError={(e) => {
          // Если картинка не загрузилась (например, битая ссылка) - скрываем её
          e.target.style.display = 'none'
        }}
      />
    )
  }

  const COLORS = [
    { bg: '#EEF2FF', text: '#4F46E5' },
    { bg: '#F0FDF4', text: '#166534' },
    { bg: '#FFFBEB', text: '#92400E' },
    { bg: '#FFF1F2', text: '#9F1239' },
    { bg: '#F0F9FF', text: '#0369A1' },
    { bg: '#FDF4FF', text: '#7E22CE' },
  ]

  const str = (name || '').trim()

  if (!str || str.toLowerCase() === 'кандидат' || str.toLowerCase() === 'null') {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: '#F3F4F6',
          color: '#9CA3AF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          border: '1.5px solid #E5E7EB',
        }}
      >
        <User size={size * 0.5} />
      </div>
    )
  }

  const color = COLORS[str.charCodeAt(0) % COLORS.length]
  const parts = str.split(' ').filter(Boolean)
  const initials = parts.length >= 2 ? parts[0][0] + parts[1][0] : str[0]

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: color.bg,
        color: color.text,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.35,
        fontWeight: 600,
        flexShrink: 0,
        border: `1.5px solid ${color.text}33`,
      }}
    >
      {initials.toUpperCase()}
    </div>
  )
}
