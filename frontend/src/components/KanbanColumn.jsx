import { useDroppable } from '@dnd-kit/core'
import KanbanCard from './KanbanCard'
import { Users } from 'lucide-react'

export default function KanbanColumn({ stage, screenings, onCardClick }) {
  const { setNodeRef, isOver } = useDroppable({
    id: stage.key,
  })

  return (
    <div
      ref={setNodeRef}
      style={{
        background: isOver ? '#F3F4F6' : '#F9FAFB',
        border: isOver ? `2px dashed ${stage.color}` : '1px solid #E5E7EB',
        borderRadius: 12,
        minWidth: 320,
        maxWidth: 340,
        height: 'fit-content',
        maxHeight: 'calc(100vh - 240px)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 200ms ease',
      }}
    >
      {/* Заголовок колонки */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid #E5E7EB',
          background: '#FFFFFF',
          borderTopLeftRadius: 12,
          borderTopRightRadius: 12,
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h3
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: '#111827',
                margin: 0,
              }}
            >
              {stage.title}
            </h3>
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: stage.color,
                background: `${stage.color}15`,
                border: `1px solid ${stage.color}30`,
                borderRadius: 999,
                padding: '2px 8px',
              }}
            >
              {screenings.length}
            </span>
          </div>
        </div>
        
        {stage.description && (
          <p
            style={{
              fontSize: 12,
              color: '#6B7280',
              margin: '4px 0 0 0',
            }}
          >
            {stage.description}
          </p>
        )}
      </div>
      
      {/* Скроллируемый список карточек */}
      <div
        style={{
          padding: 12,
          overflowY: 'auto',
          flex: 1,
          minHeight: 100, // Минимальная высота для drop zone
        }}
      >
        {screenings.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              color: '#9CA3AF',
            }}
          >
            <Users size={32} color="#D1D5DB" />
            <p
              style={{
                fontSize: 13,
                color: '#9CA3AF',
                marginTop: 12,
                textAlign: 'center',
              }}
            >
              {isOver ? 'Отпустите здесь' : 'Пока нет кандидатов'}
            </p>
          </div>
        ) : (
          screenings.map((screening) => (
            <KanbanCard
              key={screening.id}
              screening={screening}
              onClick={() => onCardClick(screening)}
            />
          ))
        )}
      </div>
    </div>
  )
}
