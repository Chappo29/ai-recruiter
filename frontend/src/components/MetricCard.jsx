export default function MetricCard({ icon: Icon, iconBg, iconColor, value, label }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #F0F0F0',
        borderRadius: 12,
        padding: 16,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: iconBg,
          color: iconColor,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 10,
        }}
      >
        <Icon size={16} />
      </div>
      <div style={{ fontSize: 24, fontWeight: 600, lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>{label}</div>
    </div>
  )
}
