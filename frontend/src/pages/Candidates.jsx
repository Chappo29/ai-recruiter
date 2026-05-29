import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Users } from 'lucide-react'
import client from '../api/client'
import KanbanBoard from '../components/KanbanBoard'
import EmptyState from '../components/EmptyState'
import { PageTopbar } from '../components/Sidebar'
import { isAiAnalysisPending } from '../utils/screeningAnalysis'

export default function Candidates() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlVacancyId = searchParams.get('vacancy_id')

  const [vacancies, setVacancies] = useState([])
  const [vacancyId, setVacancyId] = useState(urlVacancyId || '')
  const [screenings, setScreenings] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingVacancies, setLoadingVacancies] = useState(true)

  useEffect(() => {
    setLoadingVacancies(true)
    client
      .get('/vacancies/')
      .then(({ data }) => {
        setVacancies(data)
        if (urlVacancyId) {
          setVacancyId(urlVacancyId)
        } else if (!vacancyId && data.length > 0) {
          setVacancyId(data[0].id)
        }
      })
      .catch(() => setVacancies([]))
      .finally(() => setLoadingVacancies(false))
  }, [urlVacancyId])

  useEffect(() => {
    if (urlVacancyId) setVacancyId(urlVacancyId)
  }, [urlVacancyId])

  const refreshScreenings = useCallback(() => {
    if (!vacancyId) {
      setScreenings([])
      return Promise.resolve()
    }
    return client
      .get(`/screenings/vacancy/${vacancyId}`)
      .then(({ data }) => setScreenings(data))
      .catch(() => setScreenings([]))
  }, [vacancyId])

  const loadScreenings = useCallback(() => {
    if (!vacancyId) {
      setScreenings([])
      setLoading(false)
      return
    }
    setLoading(true)
    refreshScreenings().finally(() => setLoading(false))
  }, [vacancyId, refreshScreenings])

  useEffect(() => {
    loadScreenings()
  }, [loadScreenings])

  useEffect(() => {
    const hasPending = screenings.some(isAiAnalysisPending)
    if (!hasPending || !vacancyId) return undefined
    const timer = setInterval(refreshScreenings, 5000)
    return () => clearInterval(timer)
  }, [screenings, vacancyId, refreshScreenings])

  const handleStatusChange = (id, status) => {
    setScreenings((prev) =>
      prev.map((s) =>
        s.id === id
          ? {
              ...s,
              status,
              display_verdict: status,
              verdict_label: undefined,
            }
          : s
      )
    )
  }

  const selectedVacancy = vacancies.find((v) => String(v.id) === String(vacancyId))
  
  // Подсчет кандидатов в процессе AI анализа
  const aiPendingCount = screenings.filter(isAiAnalysisPending).length

  return (
    <div>
      <PageTopbar
        title="Кандидаты"
        subtitle={selectedVacancy ? selectedVacancy.title : 'Выберите вакансию'}
      />

      <div style={{ padding: 24 }}>
        <select
          value={vacancyId}
          onChange={(e) => {
            const id = e.target.value
            setVacancyId(id)
            // Сохраняем выбранную вакансию в URL, чтобы после обновления страницы выбор не терялся
            const next = new URLSearchParams(searchParams)
            if (id) {
              next.set('vacancy_id', id)
            } else {
              next.delete('vacancy_id')
            }
            navigate({ search: next.toString() }, { replace: true })
          }}
          disabled={loadingVacancies || vacancies.length === 0}
          style={{
            width: '100%',
            maxWidth: 420,
            marginBottom: 16,
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid #E5E7EB',
            fontSize: 14,
            background: '#FFFFFF',
          }}
        >
          {vacancies.length === 0 ? (
            <option value="">Нет вакансий</option>
          ) : (
            vacancies.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title}
              </option>
            ))
          )}
        </select>

        {/* Индикатор AI анализа */}
        {aiPendingCount > 0 && (
          <div
            style={{
              marginBottom: 16,
              fontSize: 13,
              color: '#6B7280',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: '#4F46E5',
                animation: 'pulse 2s infinite',
              }}
            />
            ИИ анализирует {aiPendingCount} {aiPendingCount === 1 ? 'резюме' : 'резюме'}...
          </div>
        )}

        {loading && (
          <div style={{ fontSize: 14, color: '#6B7280', padding: 40, textAlign: 'center' }}>
            Загрузка кандидатов...
          </div>
        )}

        {!loading && screenings.length === 0 && (
          <EmptyState
            icon={Users}
            title="Пока нет кандидатов"
            description="Кандидаты появятся после первых откликов через бота"
          />
        )}

        {!loading && screenings.length > 0 && (
          <KanbanBoard
            screenings={screenings}
            vacancyTitle={selectedVacancy?.title}
            onStatusChange={handleStatusChange}
          />
        )}
      </div>
    </div>
  )
}
