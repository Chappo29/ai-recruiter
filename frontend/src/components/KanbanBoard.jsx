import { useState } from 'react'
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import KanbanColumn from './KanbanColumn'
import KanbanCard from './KanbanCard'
import CandidateModal from './CandidateModal'
import RejectConfirmModal from './RejectConfirmModal'
import { PIPELINE_STAGES, groupScreeningsByStage, getStageConfig } from '../utils/pipelineStages'
import { candidateFullName } from '../utils/candidate'
import client from '../api/client'
import { useToast } from './Toast'

// Мапинг стадий на статусы для API. "scoring" не маппится — статус
// проставляется системой и не редактируется рекрутером.
const STAGE_TO_STATUS = {
  new: 'pending',
  scoring: 'scoring',
  ai_screened: 'pending',
  interview: 'forwarded',
  rejected: 'rejected',
}

export default function KanbanBoard({ screenings, vacancyTitle, onStatusChange }) {
  const [selectedScreening, setSelectedScreening] = useState(null)
  const [activeId, setActiveId] = useState(null)
  const [rejectCandidate, setRejectCandidate] = useState(null) // { screening, currentStage }
  const { showToast } = useToast()
  
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Начинаем drag после 8px движения (чтобы клик работал)
      },
    })
  )
  
  const grouped = groupScreeningsByStage(screenings, true)
  const visibleStages = PIPELINE_STAGES
  
  const activeScreening = activeId
    ? screenings.find((s) => s.id === activeId)
    : null

  const handleCardClick = (screening) => {
    setSelectedScreening(screening)
  }

  const handleCloseModal = () => {
    setSelectedScreening(null)
  }

  const handleStatusChange = (screeningId, newStatus) => {
    setSelectedScreening(null)
    onStatusChange?.(screeningId, newStatus)
  }

  const handleDragStart = (event) => {
    setActiveId(event.active.id)
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveId(null)

    if (!over) return

    const screeningId = active.id
    const newStage = over.id // ID колонки = ключ стадии

    // Находим скрининг
    const screening = screenings.find((s) => s.id === screeningId)
    if (!screening) return

    // Определяем текущую стадию
    const currentStage = Object.keys(grouped).find((stage) =>
      grouped[stage].some((s) => s.id === screeningId)
    )

    // Если стадия не изменилась, ничего не делаем
    if (currentStage === newStage) return

    // В "Оценка..." нельзя перетащить вручную — этот статус ставит система
    // (бот проводит интервью и финализирует скоринг автоматически).
    if (newStage === 'scoring') {
      showToast('В «Оценка...» статус ставится автоматически', 'info')
      return
    }

    // Если перетаскиваем в "Отклонено", показываем модалку подтверждения
    if (newStage === 'rejected') {
      setRejectCandidate({ screening, currentStage })
      return
    }

    // Определяем новый статус по стадии
    const newStatus = STAGE_TO_STATUS[newStage]
    
    // Обновляем UI сразу (optimistic update)
    onStatusChange?.(screeningId, newStatus)

    // Отправляем на сервер
    try {
      await client.patch(`/screenings/${screeningId}/status`, { status: newStatus })
      if (newStatus === 'forwarded') {
        showToast('Кандидат передан на собеседование')
      }
    } catch (error) {
      // Если ошибка, откатываем изменение
      const oldStatus = STAGE_TO_STATUS[currentStage]
      onStatusChange?.(screeningId, oldStatus)
      showToast('Не удалось обновить статус', 'error')
    }
  }

  const handleRejectConfirm = async (sendNotification) => {
    if (!rejectCandidate) return

    const { screening, currentStage } = rejectCandidate
    const screeningId = screening.id

    // Закрываем модалку
    setRejectCandidate(null)

    // Обновляем UI сразу
    onStatusChange?.(screeningId, 'rejected')

    try {
      if (sendNotification) {
        // Отправить уведомление через /reject endpoint
        await client.post(`/screenings/${screeningId}/reject`)
        showToast('Кандидат отклонён, уведомление отправлено')
      } else {
        // Просто обновить статус без уведомления
        await client.patch(`/screenings/${screeningId}/status`, { status: 'rejected' })
        showToast('Кандидат отклонён')
      }
    } catch (error) {
      // Откатываем изменение
      const oldStatus = STAGE_TO_STATUS[currentStage]
      onStatusChange?.(screeningId, oldStatus)
      
      const errorMessage = error.response?.data?.detail || 'Не удалось отклонить кандидата'
      showToast(errorMessage, 'error')
    }
  }

  const handleRejectCancel = () => {
    setRejectCandidate(null)
  }

  const handleDragCancel = () => {
    setActiveId(null)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div
        style={{
          display: 'flex',
          gap: 16,
          overflowX: 'auto',
          overflowY: 'hidden',
          paddingBottom: 16,
        }}
      >
        {visibleStages.map((stage) => (
          <KanbanColumn
            key={stage.key}
            stage={stage}
            screenings={grouped[stage.key] || []}
            onCardClick={handleCardClick}
          />
        ))}
      </div>

      {/* DragOverlay - карточка которую тащим */}
      <DragOverlay>
        {activeScreening ? (
          <div style={{ opacity: 0.8, transform: 'rotate(3deg)' }}>
            <KanbanCard screening={activeScreening} onClick={() => {}} />
          </div>
        ) : null}
      </DragOverlay>

      {selectedScreening && (
        <CandidateModal
          screening={selectedScreening}
          vacancyTitle={vacancyTitle}
          onClose={handleCloseModal}
          onStatusChange={handleStatusChange}
        />
      )}

      {rejectCandidate && (
        <RejectConfirmModal
          candidateName={candidateFullName(rejectCandidate.screening)}
          onConfirm={handleRejectConfirm}
          onCancel={handleRejectCancel}
        />
      )}
    </DndContext>
  )
}
