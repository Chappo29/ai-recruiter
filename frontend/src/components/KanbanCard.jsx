import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { Mail, FileText, Bot } from 'lucide-react'
import Avatar from './Avatar'
import { API_BASE_URL, mediaUrl } from '../api/client'
import { candidateFullName } from '../utils/candidate'
import { isAiAnalysisPending } from '../utils/screeningAnalysis'
import { screeningExtras } from '../utils/parseJSON'

function getScoreBadgeColor(score) {
  if (score >= 80) return { bg: '#DCFCE7', text: '#166534', border: '#BBF7D0' }
  if (score >= 60) return { bg: '#FEF3C7', text: '#92400E', border: '#FDE68A' }
  return { bg: '#F3F4F6', text: '#4B5563', border: '#E5E7EB' }
}

function formatTimeAgo(dateString) {
  if (!dateString) return ''
  const diff = Date.now() - new Date(dateString).getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor(diff / (1000 * 60))
  
  if (days > 0) return `${days} дн. назад`
  if (hours > 0) return `${hours} ч. назад`
  if (minutes > 0) return `${minutes} мин. назад`
  return 'Только что'
}

export default function KanbanCard({ screening, onClick }) {
  const name = candidateFullName(screening)
  const aiPending = isAiAnalysisPending(screening)
  const isRepeated = (screening.screening_index ?? 1) > 1
  const hasResume = !!screening.resume_file_path
  const hasTelegram = !!screening.candidate_telegram_id
  
  const { aiMarkers } = screeningExtras(screening)
  const isAiSuspected = aiMarkers.suspected === true
  
  const avatarSrc = mediaUrl(
    screening.avatar_url ||
      screening.candidate?.avatar_file_path ||
      screening.avatar_file_path
  )

  const scoreColors = screening.score != null ? getScoreBadgeColor(screening.score) : null

  // Drag and drop
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: screening.id,
  })

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={(e) => {
        // Если не тащим, открываем модалку
        if (!isDragging) {
          onClick()
        }
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          border: '1px solid #E5E7EB',
          borderRadius: 12,
          padding: 12,
          marginBottom: 8,
          cursor: 'pointer',
          transition: 'all 200ms ease',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          if (!isDragging) {
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
            e.currentTarget.style.transform = 'translateY(-2px)'
          }
        }}
        onMouseLeave={(e) => {
          if (!isDragging) {
            e.currentTarget.style.boxShadow = 'none'
            e.currentTarget.style.transform = 'translateY(0)'
          }
        }}
      >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <Avatar name={name} src={avatarSrc} size={40} />
        
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <h4
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: '#111827',
                margin: 0,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={name}
            >
              {name}
            </h4>
            {isRepeated && (
              <span
                style={{
                  fontSize: 10,
                  padding: '2px 6px',
                  borderRadius: 999,
                  background: '#EEF2FF',
                  color: '#4F46E5',
                  fontWeight: 500,
                  flexShrink: 0,
                }}
              >
                {screening.screening_index}
              </span>
            )}
            {isAiSuspected && (
              <div
                title="Подозрение на AI-резюме"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: '#FEF3C7',
                  border: '1px solid #FDE68A',
                  flexShrink: 0,
                }}
              >
                <Bot size={11} color="#92400E" />
              </div>
            )}
          </div>
          
          <div
            style={{
              fontSize: 11,
              color: '#9CA3AF',
              marginBottom: 8,
            }}
          >
            {formatTimeAgo(screening.created_at)}
          </div>
          
          {aiPending ? (
            <div
              style={{
                fontSize: 11,
                color: '#6B7280',
                fontStyle: 'italic',
              }}
            >
              ИИ анализирует...
            </div>
          ) : screening.score != null ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: scoreColors.text,
                  background: scoreColors.bg,
                  border: `1px solid ${scoreColors.border}`,
                  borderRadius: 999,
                  padding: '3px 10px',
                }}
              >
                {screening.score}/100
              </div>
              
              <div style={{ display: 'flex', gap: 4 }}>
                {hasResume && (
                  <FileText
                    size={14}
                    color="#9CA3AF"
                    style={{ flexShrink: 0 }}
                  />
                )}
                {hasTelegram && (
                  <Mail
                    size={14}
                    color="#9CA3AF"
                    style={{ flexShrink: 0 }}
                  />
                )}
              </div>
            </div>
          ) : (
            <div
              style={{
                fontSize: 11,
                color: '#B45309',
              }}
            >
              Без оценки
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}
