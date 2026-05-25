import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Archive, ArrowLeft, Trash2 } from 'lucide-react'
import client from '../api/client'
import CandidateCard from '../components/CandidateCard'
import CircularStatRing from '../components/CircularStatRing'
import { PageTopbar } from '../components/Sidebar'
import { CandidateCardSkeleton } from '../components/Skeleton'
import { useToast } from '../components/Toast'
import { isAiAnalysisPending } from '../utils/screeningAnalysis'

const STAT_COLORS = {
  pending: '#EAB308',
  forwarded: '#22C55E',
  rejected: '#EF4444',
}

export default function VacancyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [vacancy, setVacancy] = useState(null)
  const [stats, setStats] = useState({ pending: 0, forwarded: 0, rejected: 0, total: 0 })
  const [screenings, setScreenings] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')

  const refreshScreenings = useCallback(async () => {
    if (!id) return
    try {
      const [statsRes, scrRes] = await Promise.all([
        client.get(`/vacancies/${id}/stats`),
        client.get(`/screenings/vacancy/${id}`),
      ])
      setStats(statsRes.data)
      setScreenings(scrRes.data || [])
    } catch {
      /* keep current UI on background refresh errors */
    }
  }, [id])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [vacRes, statsRes, scrRes] = await Promise.all([
        client.get(`/vacancies/${id}`),
        client.get(`/vacancies/${id}/stats`),
        client.get(`/screenings/vacancy/${id}`),
      ])
      setVacancy(vacRes.data)
      setAiPrompt(vacRes.data.ai_screening_prompt || '')
      setStats(statsRes.data)
      setScreenings(scrRes.data || [])
    } catch {
      showToast('Не удалось загрузить вакансию', 'error')
      navigate('/vacancies')
    } finally {
      setLoading(false)
    }
  }, [id, navigate, showToast])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const hasPending = screenings.some(isAiAnalysisPending)
    if (!hasPending) return undefined
    const t = setInterval(refreshScreenings, 5000)
    return () => clearInterval(t)
  }, [screenings, refreshScreenings])

  const handleStatusChange = (screeningId, status) => {
    setScreenings((prev) =>
      prev.map((s) => (s.id === screeningId ? { ...s, status, display_verdict: status } : s))
    )
    refreshScreenings()
  }

  const savePrompt = async () => {
    setSavingPrompt(true)
    try {
      await client.patch(`/vacancies/${id}`, { ai_screening_prompt: aiPrompt || null })
      showToast('Вводные для ИИ сохранены')
      await load()
    } catch {
      showToast('Ошибка сохранения', 'error')
    } finally {
      setSavingPrompt(false)
    }
  }

  const archiveVacancy = async () => {
    if (!window.confirm('Переместить вакансию в архив?')) return
    try {
      await client.patch(`/vacancies/${id}/archive`)
      showToast('Вакансия в архиве')
      navigate('/vacancies?status=archived')
    } catch {
      showToast('Ошибка архивации', 'error')
    }
  }

  const deleteVacancy = async () => {
    if (
      !window.confirm(
        'Вы уверены? Вакансия и все отклики будут удалены безвозвратно.'
      )
    ) {
      return
    }
    try {
      await client.delete(`/vacancies/${id}`)
      showToast('Вакансия удалена')
      navigate('/vacancies')
    } catch {
      showToast('Ошибка удаления', 'error')
    }
  }

  if (loading || !vacancy) {
    return (
      <div style={{ padding: 24 }}>
        <CandidateCardSkeleton />
      </div>
    )
  }

  const isArchived = vacancy.status === 'archived'
  const statsTotal =
    stats.total ?? stats.pending + stats.forwarded + stats.rejected

  return (
    <div>
      <PageTopbar
        title={vacancy.title}
        subtitle={`${vacancy.company}${isArchived ? ' · Архив' : ''}`}
      >
        <button
          type="button"
          onClick={() => navigate('/vacancies')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 12px',
            border: '1px solid #E5E7EB',
            borderRadius: 8,
            background: '#FFF',
            fontSize: 13,
          }}
        >
          <ArrowLeft size={16} /> Назад
        </button>
        {!isArchived && (
          <button
            type="button"
            onClick={archiveVacancy}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 12px',
              border: '1px solid #E5E7EB',
              borderRadius: 8,
              background: '#FFF',
              fontSize: 13,
            }}
          >
            <Archive size={16} /> В архив
          </button>
        )}
        <button
          type="button"
          onClick={deleteVacancy}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 12px',
            border: 'none',
            borderRadius: 8,
            background: '#FEE2E2',
            color: '#B91C1C',
            fontSize: 13,
          }}
        >
          <Trash2 size={16} /> Удалить
        </button>
      </PageTopbar>

      <div style={{ padding: 24 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 12,
            marginBottom: 24,
          }}
        >
          <CircularStatRing
            label="На рассмотрении"
            value={stats.pending}
            total={statsTotal}
            color={STAT_COLORS.pending}
          />
          <CircularStatRing
            label="Передан дальше"
            value={stats.forwarded}
            total={statsTotal}
            color={STAT_COLORS.forwarded}
          />
          <CircularStatRing
            label="Отказ"
            value={stats.rejected}
            total={statsTotal}
            color={STAT_COLORS.rejected}
          />
        </div>

        <div
          style={{
            background: '#FFFFFF',
            border: '1px solid #F0F0F0',
            borderRadius: 12,
            padding: 16,
            marginBottom: 24,
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Описание</h2>
          {vacancy.hh_url && (
            <p style={{ fontSize: 13, marginBottom: 8 }}>
              <a href={vacancy.hh_url} target="_blank" rel="noreferrer">
                {vacancy.hh_url}
              </a>
            </p>
          )}
          <p style={{ fontSize: 13, color: '#374151', whiteSpace: 'pre-wrap' }}>
            {vacancy.description || vacancy.requirements || '—'}
          </p>

          <h2 style={{ fontSize: 14, fontWeight: 600, margin: '20px 0 8px' }}>
            Вводные для ИИ
          </h2>
          <textarea
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            rows={4}
            placeholder="На что обратить внимание в диалоге с кандидатом…"
            style={{
              width: '100%',
              border: '1px solid #E5E7EB',
              borderRadius: 8,
              padding: 12,
              fontSize: 13,
              marginBottom: 8,
            }}
          />
          <button
            type="button"
            onClick={savePrompt}
            disabled={savingPrompt}
            style={{
              padding: '8px 14px',
              background: '#4F46E5',
              color: '#FFF',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
            }}
          >
            {savingPrompt ? 'Сохранение…' : 'Сохранить вводные'}
          </button>
        </div>

        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Кандидаты</h2>
        {screenings.length === 0 && (
          <p style={{ color: '#9CA3AF', fontSize: 14 }}>Пока нет откликов</p>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {screenings.map((s) => (
            <CandidateCard
              key={s.id}
              screening={s}
              vacancyTitle={vacancy.title}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
