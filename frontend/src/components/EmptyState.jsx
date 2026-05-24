export default function EmptyState({ icon: Icon, title, description }) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '48px 24px',
        background: '#FFFFFF',
        border: '1px solid #F0F0F0',
        borderRadius: 12,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      {Icon && (
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 12,
            background: '#F3F4F6',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#9CA3AF',
            marginBottom: 16,
          }}
        >
          <Icon size={28} />
        </div>
      )}
      <h3 style={{ fontSize: 16, fontWeight: 600, color: '#111827', marginBottom: 8 }}>
        {title}
      </h3>
      <p style={{ fontSize: 14, color: '#6B7280', maxWidth: 360, margin: '0 auto' }}>
        {description}
      </p>
    </div>
  )
}
