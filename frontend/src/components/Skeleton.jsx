const block = {
  background: 'linear-gradient(90deg, #F3F4F6 25%, #E5E7EB 50%, #F3F4F6 75%)',
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.2s ease-in-out infinite',
  borderRadius: 8,
}

export function Skeleton({ width = '100%', height = 16, style = {} }) {
  return <div style={{ width, height, ...block, ...style }} />
}

export function CandidateCardSkeleton() {
  return (
    <div
      style={{
        background: '#FFFFFF',
        border: '1px solid #F0F0F0',
        borderRadius: 12,
        padding: 16,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <Skeleton width={48} height={48} style={{ borderRadius: '50%' }} />
        <div style={{ flex: 1 }}>
          <Skeleton width="40%" height={18} style={{ marginBottom: 8 }} />
          <Skeleton width="60%" height={14} />
        </div>
      </div>
      <Skeleton height={8} style={{ marginBottom: 16 }} />
      <Skeleton height={60} style={{ marginBottom: 8 }} />
      <Skeleton height={40} />
    </div>
  )
}

export function TableRowSkeleton() {
  return (
    <tr>
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <td key={i} style={{ padding: '14px 16px' }}>
          <Skeleton height={14} />
        </td>
      ))}
    </tr>
  )
}

export function MetricSkeleton() {
  return (
    <div
      style={{
        background: '#FFFFFF',
        border: '1px solid #F0F0F0',
        borderRadius: 12,
        padding: 16,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      <Skeleton width={32} height={32} style={{ marginBottom: 12 }} />
      <Skeleton width="50%" height={24} style={{ marginBottom: 8 }} />
      <Skeleton width="70%" height={14} />
    </div>
  )
}
