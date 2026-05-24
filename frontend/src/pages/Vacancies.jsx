import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Briefcase, Plus } from 'lucide-react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import { TableRowSkeleton } from '../components/Skeleton'

const inputStyle = {
  width: '100%',
  border: '1px solid #E5E7EB',
  borderRadius: 8,
  padding: '10px 14px',
  fontSize: 14,
  marginBottom: 12,
  background: '#FFFFFF',
}

function vacancyCompany(v) {
  return v.company?.trim() || '—'
}

export default function Vacancies() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [vacancies, setVacancies] = useState([])
  const [statsByVacancy, setStatsByVacancy] = useState({})
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [hhUrl, setHhUrl] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [requirements, setRequirements] = useState('')
  const [description, setDescription] = useState('')
  const [preview, setPreview] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [{ data: vacs }, { data: stats }] = await Promise.all([
        client.get('/vacancies/'),
        client.get('/screenings/stats'),
      ])
      setVacancies(vacs)
      const map = {}
      ;(stats || []).forEach((row) => {
        map[row.vacancy_id] = row
      })
      setStatsByVacancy(map)
    } catch {
      showToast('Не удалось загрузить вакансии', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const stats = useMemo(() => {
    const map = {}
    vacancies.forEach((v) => {
      const row = statsByVacancy[v.id]
      map[v.id] = {
        total: row?.total ?? 0,
        fit: row?.fit ?? 0,
      }
    })
    return map
  }, [vacancies, statsByVacancy])

  const parseHh = async () => {
    if (!hhUrl.trim()) {
      showToast('Введите ссылку на hh.ru', 'error')
      return
    }
    setParsing(true)
    try {
      const { data } = await client.post('/vacancies/parse-hh', { hh_url: hhUrl })
      setTitle(data.title || '')
      setCompany(data.company || '')
      setRequirements(data.requirements || '')
      setDescription(data.description || '')
      setPreview(data)
      showToast('Вакансия загружена с hh.ru')
    } catch {
      showToast('Не удалось загрузить вакансию', 'error')
    } finally {
      setParsing(false)
    }
  }

  const resetModal = () => {
    setHhUrl('')
    setTitle('')
    setCompany('')
    setRequirements('')
    setDescription('')
    setPreview(null)
  }

  const createVacancy = async () => {
    if (!title.trim()) {
      showToast('Укажите название вакансии', 'error')
      return
    }
    setSaving(true)
    try {
      await client.post('/vacancies/', {
        title: title.trim(),
        company: company.trim() || null,
        hh_url: hhUrl || null,
        requirements: requirements || null,
        description: description || null,
      })
      showToast('Вакансия создана')
      setModalOpen(false)
      resetModal()
      await load()
    } catch {
      showToast('Ошибка создания вакансии', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <h1 style={{ fontSize: 20, fontWeight: 600, color: '#111827' }}>Вакансии</h1>
        <button
          type="button"
          onClick={() => {
            resetModal()
            setModalOpen(true)
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 14px',
            background: '#4F46E5',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          <Plus size={16} /> Добавить вакансию
        </button>
      </div>

      <div
        style={{
          background: '#FFFFFF',
          border: '1px solid #F0F0F0',
          borderRadius: 12,
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          overflow: 'hidden',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#F9FAFB', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Вакансия</th>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Компания</th>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Кандидатов</th>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Fit</th>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Статус</th>
              <th style={{ padding: '12px 16px', fontWeight: 500, color: '#6B7280' }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [1, 2, 3, 4].map((i) => <TableRowSkeleton key={i} />)}
            {!loading &&
              vacancies.map((v) => {
                const st = stats[v.id] || { total: 0, fit: 0 }
                return (
                  <tr
                    key={v.id}
                    style={{
                      borderTop: '1px solid #F0F0F0',
                      cursor: 'pointer',
                    }}
                    onClick={() => navigate(`/candidates?vacancy_id=${v.id}`)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#F9FAFB'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#FFFFFF'
                    }}
                  >
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 8,
                            background: '#EEF2FF',
                            color: '#4F46E5',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Briefcase size={14} />
                        </div>
                        {v.title}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#6B7280' }}>
                      {vacancyCompany(v)}
                    </td>
                    <td style={{ padding: '12px 16px' }}>{st.total}</td>
                    <td style={{ padding: '12px 16px', color: '#166534', fontWeight: 500 }}>
                      {st.fit}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span
                        style={{
                          fontSize: 11,
                          padding: '4px 8px',
                          borderRadius: 999,
                          background: v.status === 'active' ? '#F0FDF4' : '#F9FAFB',
                          color: v.status === 'active' ? '#166534' : '#9CA3AF',
                        }}
                      >
                        {v.status === 'active' ? 'Активна' : 'Закрыта'}
                      </span>
                    </td>
                    <td
                      style={{ padding: '12px 16px', color: '#4F46E5', fontSize: 13 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: '#4F46E5',
                          fontSize: 13,
                        }}
                        onClick={() => navigate(`/candidates?vacancy_id=${v.id}`)}
                      >
                        Кандидаты →
                      </button>
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
        {!loading && vacancies.length === 0 && (
          <p style={{ padding: 24, textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
            Добавьте первую вакансию
          </p>
        )}
      </div>

      {modalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: 16,
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 520,
              maxHeight: '90vh',
              overflowY: 'auto',
              background: '#FFFFFF',
              borderRadius: 12,
              padding: 24,
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Новая вакансия</h2>

            <label style={{ fontSize: 13, color: '#6B7280' }}>Ссылка hh.ru</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                value={hhUrl}
                onChange={(e) => setHhUrl(e.target.value)}
                placeholder="https://hh.ru/vacancy/..."
                style={{ ...inputStyle, marginBottom: 0, flex: 1 }}
              />
              <button
                type="button"
                onClick={parseHh}
                disabled={parsing}
                style={{
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid #E5E7EB',
                  background: '#FFFFFF',
                  whiteSpace: 'nowrap',
                  fontSize: 13,
                }}
              >
                {parsing ? 'Загрузка…' : 'Загрузить с hh.ru'}
              </button>
            </div>

            {preview && (
              <div
                style={{
                  marginBottom: 16,
                  padding: 12,
                  borderRadius: 8,
                  background: '#F9FAFB',
                  border: '1px solid #F0F0F0',
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Превью с hh.ru</div>
                <div>
                  <strong>{preview.title || '—'}</strong>
                  {preview.company && (
                    <span style={{ color: '#6B7280' }}> · {preview.company}</span>
                  )}
                </div>
                {preview.salary && (
                  <div style={{ color: '#6B7280', marginTop: 4 }}>{preview.salary}</div>
                )}
                {preview.requirements && (
                  <p
                    style={{
                      marginTop: 8,
                      color: '#374151',
                      maxHeight: 80,
                      overflow: 'hidden',
                    }}
                  >
                    {preview.requirements.slice(0, 200)}
                    {preview.requirements.length > 200 ? '…' : ''}
                  </p>
                )}
              </div>
            )}

            <input
              placeholder="Название вакансии"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={inputStyle}
            />
            <input
              placeholder="Компания"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              style={inputStyle}
            />
            <textarea
              placeholder="Требования"
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              rows={3}
              style={{ ...inputStyle, resize: 'vertical' }}
            />
            <textarea
              placeholder="Описание"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              style={{ ...inputStyle, resize: 'vertical' }}
            />

            <button
              type="button"
              onClick={createVacancy}
              disabled={saving}
              style={{
                width: '100%',
                padding: 11,
                background: '#4F46E5',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: 8,
                fontWeight: 500,
              }}
            >
              {saving ? 'Создание…' : 'Создать'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
