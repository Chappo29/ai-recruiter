const VERDICTS = {
  pending: { label: 'На рассмотрении', bg: '#F3F4F6', color: '#6B7280' },
  forwarded: { label: 'Передан дальше', bg: '#EEF2FF', color: '#4F46E5' },
  rejected: { label: 'Отказ', bg: '#FFF1F2', color: '#9F1239' },
  fit: { label: 'Подходит (ИИ)', bg: '#F0FDF4', color: '#166534' },
  maybe: { label: 'Возможно (ИИ)', bg: '#FFFBEB', color: '#92400E' },
  reject: { label: 'Не подходит (ИИ)', bg: '#FFF1F2', color: '#9F1239' },
}

export default function VerdictBadge({ verdict, label }) {
  const key = (verdict || 'pending').toLowerCase()
  const v = VERDICTS[key] || VERDICTS.pending
  const text = label || v.label
  return (
    <span
      style={{
        background: v.bg,
        color: v.color,
        padding: '3px 10px',
        borderRadius: 20,
        fontSize: 12,
        fontWeight: 600,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        flexShrink: 0,
      }}
    >
      {text}
    </span>
  )
}
