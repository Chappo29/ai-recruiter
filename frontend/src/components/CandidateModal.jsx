import { X } from 'lucide-react'
import { useEffect } from 'react'
import CandidateCard from './CandidateCard'

export default function CandidateModal({ screening, vacancyTitle, onClose, onStatusChange }) {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'
    
    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [onClose])

  return (
    <div
      onClick={onClose}
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
        zIndex: 9999,
        padding: 20,
        animation: 'fadeIn 200ms ease-out',
      }}
    >
      <style>
        {`
          @keyframes fadeIn {
            from {
              opacity: 0;
            }
            to {
              opacity: 1;
            }
          }
          @keyframes scaleIn {
            from {
              transform: scale(0.95);
              opacity: 0;
            }
            to {
              transform: scale(1);
              opacity: 1;
            }
          }
        `}
      </style>
      
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#FFFFFF',
          borderRadius: 16,
          maxWidth: 680,
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          position: 'relative',
          animation: 'scaleIn 250ms cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
        }}
      >
        {/* Кнопка закрытия */}
        <button
          onClick={onClose}
          style={{
            position: 'sticky',
            top: 0,
            right: 0,
            float: 'right',
            margin: 16,
            padding: 8,
            border: 'none',
            background: '#F3F4F6',
            borderRadius: 8,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 150ms',
            zIndex: 10,
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
        
        {/* Контент - переиспользуем CandidateCard */}
        <div style={{ clear: 'both' }}>
          <CandidateCard
            screening={screening}
            vacancyTitle={vacancyTitle}
            onStatusChange={onStatusChange}
          />
        </div>
      </div>
    </div>
  )
}
