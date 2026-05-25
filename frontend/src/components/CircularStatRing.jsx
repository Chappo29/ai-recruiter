const RING_SIZE = 112
const STROKE = 8

function ringGeometry(size, stroke) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  return { radius, circumference, center: size / 2 }
}

export default function CircularStatRing({ label, value, total, color }) {
  const count = value ?? 0
  const sum = total > 0 ? total : 0
  const percent = sum > 0 ? Math.round((count / sum) * 100) : 0
  const { radius, circumference, center } = ringGeometry(RING_SIZE, STROKE)
  const dashOffset = circumference - (percent / 100) * circumference

  return (
    <div
      style={{
        flex: 1,
        minWidth: 140,
        background: '#FFFFFF',
        border: '1px solid #F0F0F0',
        borderRadius: 12,
        padding: '20px 16px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ position: 'relative', width: RING_SIZE, height: RING_SIZE }}>
        <svg
          width={RING_SIZE}
          height={RING_SIZE}
          style={{ transform: 'rotate(-90deg)', display: 'block' }}
          aria-hidden
        >
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#F3F4F6"
            strokeWidth={STROKE}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            style={{ transition: 'stroke-dashoffset 0.4s ease' }}
          />
        </svg>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <span style={{ fontSize: 26, fontWeight: 700, color: '#111827', lineHeight: 1 }}>
            {count}
          </span>
          {sum > 0 && (
            <span style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{percent}%</span>
          )}
        </div>
      </div>
      <div
        style={{
          marginTop: 12,
          fontSize: 13,
          fontWeight: 500,
          color: '#374151',
          textAlign: 'center',
        }}
      >
        {label}
      </div>
    </div>
  )
}
