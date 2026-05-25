export function scoreColor(score) {
  if (score == null) return '#9CA3AF'
  if (score > 70) return '#22C55E'
  if (score >= 40) return '#F59E0B'
  return '#F43F5E'
}

export default function ScoreBar({
  score,
  showLabel = true,
  pending = false,
  missing = false,
}) {
  if (pending && score == null) {
    return (
      <div>
        {showLabel && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              color: '#6B7280',
              marginBottom: 6,
            }}
          >
            <span>Оценка</span>
          </div>
        )}
        <div
          className="score-skeleton"
          style={{
            height: 8,
            borderRadius: 999,
            background: 'linear-gradient(90deg, #F3F4F6 25%, #E5E7EB 50%, #F3F4F6 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.2s ease-in-out infinite',
          }}
        />
      </div>
    )
  }

  const value = score ?? 0
  const color = scoreColor(score)
  const labelRight =
    score != null ? `${score}/100` : missing ? 'Нет оценки' : '—'

  return (
    <div>
      {showLabel && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 12,
            color: '#6B7280',
            marginBottom: 6,
          }}
        >
          <span>Оценка</span>
          <span
            style={{
              fontWeight: 600,
              color: missing ? '#B45309' : '#111827',
            }}
          >
            {labelRight}
          </span>
        </div>
      )}
      <div
        style={{
          height: 8,
          borderRadius: 999,
          background: '#F3F4F6',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, value))}%`,
            height: '100%',
            background: color,
            borderRadius: 999,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
