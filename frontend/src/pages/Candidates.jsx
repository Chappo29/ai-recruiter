import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Users } from 'lucide-react'
import client from '../api/client'
import CandidateCard from '../components/CandidateCard'
import EmptyState from '../components/EmptyState'
import { CandidateCardSkeleton } from '../components/Skeleton'
import { PageTopbar } from '../components/Sidebar'
import { screeningHrStatus, screeningVerdict } from '../utils/candidate'
import { isAiAnalysisPending } from '../utils/screeningAnalysis'

const FILTERS = [
  { key: 'all', label: 'Все' },
  { key: 'pending', label: 'На рассмотрении' },
  { key: 'forwarded', label: 'Передан дальше' },
  { key: 'rejected', label: 'Отказ' },
  { key: 'repeated', label: 'Повторные' },
]

export default function Candidates() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlVacancyId = searchParams.get('vacancy_id')

  const [vacancies, setVacancies] = useState([])
  const [vacancyId, setVacancyId] = useState(urlVacancyId || '')
  const [screenings, setScreenings] = useState([])
  const [filter, setFilter] = useState('all')
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

  const filtered = screenings.filter((s) => {
    if (filter === 'all') return true
    if (filter === 'repeated') return (s.screening_index ?? 1) > 1
    return screeningHrStatus(s) === filter
  })

  const showVacancySelect = !urlVacancyId

  return (
    <div>
      <PageTopbar
        title="Кандидаты"
        subtitle={selectedVacancy ? selectedVacancy.title : 'Выберите вакансию'}
      />

      <div style={{ padding: 24 }}>
        {showVacancySelect && (
          <select
            value={vacancyId}
            onChange={(e) => {
              const id = e.target.value
              setVacancyId(id)
              navigate(id ? `/candidates?vacancy_id=${id}` : '/candidates', { replace: true })
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
        )}

        {urlVacancyId && selectedVacancy && (
          <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 16 }}>
            Вакансия: <strong style={{ color: '#111827' }}>{selectedVacancy.title}</strong>
          </p>
        )}

        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              style={{
                padding: '6px 14px',
                borderRadius: 999,
                border: filter === f.key ? 'none' : '1px solid #E5E7EB',
                background: filter === f.key ? '#4F46E5' : '#FFFFFF',
                color: filter === f.key ? '#FFFFFF' : '#374151',
                fontSize: 13,
                fontWeight: filter === f.key ? 500 : 400,
              }}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading && (
          <div style={{ display: 'grid', gap: 16, maxWidth: 720 }}>
            {[1, 2, 3].map((i) => (
              <CandidateCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <EmptyState
            icon={Users}
            title="Пока нет кандидатов"
            description="Кандидаты появятся после первых откликов через бота"
          />
        )}

        {!loading && filtered.length > 0 && (
          <div
            style={{
              display: 'grid',
              gap: 16,
              maxWidth: 720,
            }}
          >
            {filtered.map((s) => (
              <CandidateCard
                key={s.id}
                screening={s}
                vacancyTitle={selectedVacancy?.title}
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
