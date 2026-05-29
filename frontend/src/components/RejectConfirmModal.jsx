import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function RejectConfirmModal({ candidateName, onConfirm, onCancel }) {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'
    
    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [onCancel])

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: 20,
        animation: 'fadeIn 200ms ease-out',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#FFFFFF',
          borderRadius: 16,
          maxWidth: 480,
          width: '100%',
          padding: 24,
          position: 'relative',
          animation: 'scaleIn 250ms cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
        }}
      >
        <button
          onClick={onCancel}
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            padding: 8,
            border: 'none',
            background: '#F3F4F6',
            borderRadius: 8,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 150ms',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#E5E7EB'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#F3F4F6'
          }}
        >
          <X size={20} color="#6B7280" />
        </button>

        <h2
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: '#111827',
            marginBottom: 12,
            marginTop: 0,
          }}
        >
          Отклонить кандидата?
        </h2>

        <p
          style={{
            fontSize: 14,
            color: '#6B7280',
            marginBottom: 24,
            lineHeight: 1.5,
          }}
        >
          Вы уверены, что хотите отклонить кандидата <strong>{candidateName}</strong>?
        </p>

        <div
          style={{
            padding: 16,
            background: '#FEF3C7',
            border: '1px solid #FDE68A',
            borderRadius: 8,
            marginBottom: 24,
          }}
        >
          <p
            style={{
              fontSize: 13,
              color: '#92400E',
              margin: 0,
              fontWeight: 500,
            }}
          >
            ⚠️ Отправить уведомление об отказе кандидату в Telegram?
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button
            onClick={() => onConfirm(true)}
            style={{
              flex: 1,
              minWidth: 140,
              padding: '12px 20px',
              borderRadius: 8,
              border: '1px solid #FECACA',
              background: '#FEE2E2',
              fontSize: 14,
              fontWeight: 500,
              color: '#991B1B',
              cursor: 'pointer',
              transition: 'all 150ms',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FEF2F2'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FEE2E2'
            }}
          >
            Да, отправить уведомление
          </button>

          <button
            onClick={() => onConfirm(false)}
            style={{
              flex: 1,
              minWidth: 140,
              padding: '12px 20px',
              borderRadius: 8,
              border: '1px solid #E5E7EB',
              background: '#FFFFFF',
              fontSize: 14,
              fontWeight: 500,
              color: '#374151',
              cursor: 'pointer',
              transition: 'all 150ms',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#F9FAFB'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFFFFF'
            }}
          >
            Нет, отклонить без уведомления
          </button>
        </div>

        <button
          onClick={onCancel}
          style={{
            width: '100%',
            marginTop: 12,
            padding: '10px 20px',
            borderRadius: 8,
            border: 'none',
            background: 'transparent',
            fontSize: 13,
            fontWeight: 500,
            color: '#6B7280',
            cursor: 'pointer',
            transition: 'color 150ms',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#111827'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = '#6B7280'
          }}
        >
          Отмена
        </button>
      </div>
    </div>
  )
}
