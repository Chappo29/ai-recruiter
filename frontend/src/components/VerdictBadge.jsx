const VERDICTS = {
  fit: { label: 'Подходит', bg: '#F0FDF4', color: '#166534' },
  maybe: { label: 'На рассмотрении', bg: '#FFFBEB', color: '#92400E' },
  reject: { label: 'Не подходит', bg: '#FFF1F2', color: '#9F1239' },
  rejected: { label: 'Отказ отправлен', bg: '#F9FAFB', color: '#6B7280' },
  pending: { label: 'Обработка…', bg: '#F3F4F6', color: '#6B7280', pending: true },
  failed: { label: 'Ошибка ИИ', bg: '#FFFBEB', color: '#B45309' },
}

export default function VerdictBadge({ verdict }) {
  const v = VERDICTS[verdict] || VERDICTS.maybe
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
      }}
    >
      {v.pending && <span className="verdict-loader" aria-hidden />}
      {v.label}
    </span>
  )
}
