import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, ChevronDown, ChevronRight, Plus, Search } from 'lucide-react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import EmptyState from '../components/EmptyState'
import { Briefcase } from 'lucide-react'
import { PageTopbar } from '../components/Sidebar'

// Deterministic color from string
const COMPANY_COLORS = [
  ['#6366F1', '#8B5CF6'],
  ['#10B981', '#059669'],
  ['#F59E0B', '#D97706'],
  ['#EC4899', '#DB2777'],
  ['#14B8A6', '#0D9488'],
  ['#3B82F6', '#2563EB'],
  ['#EF4444', '#DC2626'],
  ['#8B5CF6', '#7C3AED'],
]

function companyColor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return COMPANY_COLORS[Math.abs(hash) % COMPANY_COLORS.length]
}

function CompanyAvatar({ name, size = 32 }) {
  const [from, to] = companyColor(name)
  const initial = (name || '?')[0].toUpperCase()
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 8,
        background: `linear-gradient(135deg, ${from}, ${to})`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.45,
        fontWeight: 700,
        color: '#fff',
        flexShrink: 0,
      }}
    >
      {initial}
    </div>
  )
}

function FunnelBar({ total, pending }) {
  const max = Math.max(total, 10)
  const pctTotal = Math.min((total / max) * 100, 100)
  const pctPending = total > 0 ? Math.min((pending / total) * 100, 100) : 0

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div
        style={{
          width: 80,
          height: 6,
          borderRadius: 999,
          background: '#F0F0F0',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${pctTotal}%`,
            background: '#E0E7FF',
            borderRadius: 999,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${(pctPending / 100) * pctTotal}%`,
            background: '#6366F1',
            borderRadius: 999,
          }}
        />
      </div>
      <span style={{ fontSize: 12, color: '#9CA3AF', whiteSpace: 'nowrap', minWidth: 60 }}>
        {total} канд.
      </span>
    </div>
  )
}

const inputStyle = {
  width: '100%',
  border: '1px solid #E5E7EB',
  borderRadius: 8,
  padding: '10px 14px',
  fontSize: 14,
  marginBottom: 12,
  background: '#FFFFFF',
  outline: 'none',
}

function vacancyCompany(v) {
  return v.company?.trim() || 'Без компании'
}

export default function Vacancies() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const tab = searchParams.get('status') === 'archived' ? 'archived' : 'active'
  const { showToast } = useToast()

  const [vacancies, setVacancies] = useState([])
  const [statsByVacancy, setStatsByVacancy] = useState({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState({})

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [hhUrl, setHhUrl] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [requirements, setRequirements] = useState('')
  const [description, setDescription] = useState('')
  const [aiScreeningPrompt, setAiScreeningPrompt] = useState('')
  const [preview, setPreview] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [hhFallbackOpen, setHhFallbackOpen] = useState(false)
  const [hhPaste, setHhPaste] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [{ data: vacs }, { data: stats }] = await Promise.all([
        client.get('/vacancies/', { params: { status: tab === 'archived' ? 'archived' : undefined } }),
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
  }, [tab])

  const statsMap = useMemo(() => {
    const map = {}
    vacancies.forEach((v) => {
      const row = statsByVacancy[v.id]
      map[v.id] = { total: row?.total ?? 0, pending: row?.pending ?? 0 }
    })
    return map
  }, [vacancies, statsByVacancy])

  // Filter + group
  const groups = useMemo(() => {
    const q = search.toLowerCase()
    const filtered = vacancies.filter(
      (v) =>
        !q ||
        v.title.toLowerCase().includes(q) ||
        vacancyCompany(v).toLowerCase().includes(q)
    )
    const map = {}
    filtered.forEach((v) => {
      const co = vacancyCompany(v)
      if (!map[co]) map[co] = []
      map[co].push(v)
    })
    return Object.entries(map).sort((a, b) => a[0].localeCompare(b[0]))
  }, [vacancies, search])

  const toggleGroup = (co) =>
    setCollapsedGroups((prev) => ({ ...prev, [co]: !prev[co] }))

  function parsePastedVacancyText(text) {
    const raw = (text || '').trim()
    if (!raw) return { requirements: '', description: '' }
    const normalized = raw.replace(/\r/g, '').replace(/[ \t]+\n/g, '\n').trim()
    const reqMarkers = ['требования', 'ожидаем от вас', 'мы ожидаем', 'что мы ждём']
    const descMarkers = ['обязанности', 'задачи', 'чем предстоит', 'чем заниматься', 'описание']
    const lines = normalized.split('\n')
    const lowerLines = lines.map((l) => l.trim().toLowerCase())
    let reqIdx = -1
    let descIdx = -1
    for (let i = 0; i < lowerLines.length; i += 1) {
      const l = lowerLines[i]
      if (reqIdx === -1 && reqMarkers.some((m) => l === m || l.startsWith(`${m}:`))) reqIdx = i
      if (descIdx === -1 && descMarkers.some((m) => l === m || l.startsWith(`${m}:`))) descIdx = i
    }
    if (reqIdx !== -1 || descIdx !== -1) {
      const first = reqIdx !== -1 ? reqIdx : descIdx
      if (reqIdx !== -1 && descIdx !== -1) {
        if (descIdx < reqIdx)
          return {
            description: lines.slice(descIdx + 1, reqIdx).join('\n').trim(),
            requirements: lines.slice(reqIdx + 1).join('\n').trim(),
          }
        return {
          requirements: lines.slice(reqIdx + 1, descIdx).join('\n').trim(),
          description: lines.slice(descIdx + 1).join('\n').trim(),
        }
      }
      const content = lines.slice(first + 1).join('\n').trim()
      return {
        requirements: reqIdx !== -1 ? content : '',
        description: descIdx !== -1 ? content : normalized,
      }
    }
    return { requirements: '', description: normalized }
  }

  const parseHh = async () => {
    if (!hhUrl.trim()) { showToast('Введите ссылку на hh.ru', 'error'); return }
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
      setHhFallbackOpen(true)
      showToast('Автозаполнение не сработало. Вставьте текст вакансии вручную.', 'error')
    } finally {
      setParsing(false)
    }
  }

  const resetModal = () => {
    setHhUrl(''); setTitle(''); setCompany(''); setRequirements('')
    setDescription(''); setAiScreeningPrompt(''); setPreview(null)
    setHhFallbackOpen(false); setHhPaste('')
  }

  const createVacancy = async () => {
    if (!title.trim()) { showToast('Укажите название вакансии', 'error'); return }
    if (!company.trim()) { showToast('Укажите компанию', 'error'); return }
    setSaving(true)
    try {
      await client.post('/vacancies/', {
        title: title.trim(),
        company: company.trim(),
        hh_url: hhUrl || null,
        requirements: requirements || null,
        description: description || null,
        ai_screening_prompt: aiScreeningPrompt.trim() || null,
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

  const totalActive = vacancies.filter((v) => v.status === 'active').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageTopbar
        title="Вакансии"
        subtitle={
          tab === 'active'
            ? `${totalActive} активных вакансий`
            : 'Архив закрытых вакансий'
        }
      >
        <button
          type="button"
          onClick={() => { resetModal(); setModalOpen(true) }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            background: '#4F46E5',
            color: '#fff',
            border: 'none',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          <Plus size={15} /> Добавить вакансию
        </button>
      </PageTopbar>

      <div style={{ padding: '16px 24px 0', display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Tabs */}
        <div
          style={{
            display: 'flex',
            background: '#F3F4F6',
            borderRadius: 10,
            padding: 3,
            gap: 2,
          }}
        >
          {[
            { key: 'active', label: 'Активные' },
            { key: 'archived', label: 'Архив' },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => navigate(key === 'archived' ? '/vacancies?status=archived' : '/vacancies')}
              style={{
                padding: '6px 16px',
                borderRadius: 8,
                border: 'none',
                background: tab === key ? '#fff' : 'transparent',
                color: tab === key ? '#111827' : '#6B7280',
                fontSize: 13,
                fontWeight: tab === key ? 500 : 400,
                cursor: 'pointer',
                boxShadow: tab === key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
          <Search
            size={14}
            style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: '#9CA3AF' }}
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию или компании…"
            style={{
              width: '100%',
              padding: '8px 12px 8px 32px',
              border: '1px solid #E5E7EB',
              borderRadius: 9,
              fontSize: 13,
              background: '#fff',
              outline: 'none',
              color: '#111827',
            }}
          />
        </div>
      </div>

      <div style={{ padding: '16px 24px 40px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading && (
          <div style={{ padding: '40px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
            Загрузка…
          </div>
        )}

        {!loading && groups.length === 0 && (
          <EmptyState
            icon={Briefcase}
            title="Нет вакансий"
            description={
              search
                ? 'Ничего не найдено по вашему запросу'
                : 'Добавьте первую вакансию, нажав кнопку выше'
            }
          />
        )}

        {!loading &&
          groups.map(([companyName, vacs]) => {
            const collapsed = collapsedGroups[companyName]
            const [from, to] = companyColor(companyName)
            return (
              <div
                key={companyName}
                style={{
                  background: '#fff',
                  border: '1px solid #EBEBEB',
                  borderRadius: 12,
                  overflow: 'hidden',
                }}
              >
                {/* Group header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(companyName)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '12px 16px',
                    background: '#FAFAFA',
                    border: 'none',
                    borderBottom: collapsed ? 'none' : '1px solid #F0F0F0',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <CompanyAvatar name={companyName} size={30} />
                  <span style={{ fontWeight: 600, fontSize: 14, color: '#111827', flex: 1 }}>
                    {companyName}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      color: '#6B7280',
                      background: '#F0F0F0',
                      padding: '2px 8px',
                      borderRadius: 999,
                    }}
                  >
                    {vacs.length} {vacs.length === 1 ? 'вакансия' : vacs.length < 5 ? 'вакансии' : 'вакансий'}
                  </span>
                  {collapsed ? (
                    <ChevronRight size={16} color="#9CA3AF" />
                  ) : (
                    <ChevronDown size={16} color="#9CA3AF" />
                  )}
                </button>

                {/* Vacancy rows */}
                {!collapsed && (
                  <div>
                    {vacs.map((v, idx) => {
                      const st = statsMap[v.id] || { total: 0, pending: 0 }
                      const isActive = v.status === 'active'
                      return (
                        <div
                          key={v.id}
                          onClick={() => navigate(`/vacancies/${v.id}`)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 16,
                            padding: '13px 16px 13px 0',
                            borderTop: idx > 0 ? '1px solid #F5F5F5' : 'none',
                            cursor: 'pointer',
                            transition: 'background 0.12s',
                            position: 'relative',
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = '#F9FAFB' }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                        >
                          {/* Status accent bar */}
                          <div
                            style={{
                              width: 3,
                              alignSelf: 'stretch',
                              minHeight: 36,
                              borderRadius: '0 2px 2px 0',
                              background: isActive
                                ? `linear-gradient(${from}, ${to})`
                                : '#E5E7EB',
                              flexShrink: 0,
                            }}
                          />

                          {/* Title + status */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 14,
                                fontWeight: 500,
                                color: '#111827',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {v.title}
                            </div>
                            <div style={{ marginTop: 3 }}>
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 500,
                                  padding: '2px 7px',
                                  borderRadius: 999,
                                  background: isActive ? '#F0FDF4' : '#F3F4F6',
                                  color: isActive ? '#15803D' : '#9CA3AF',
                                }}
                              >
                                {isActive ? '● Активна' : v.status === 'archived' ? 'В архиве' : 'Закрыта'}
                              </span>
                            </div>
                          </div>

                          {/* Funnel bar */}
                          <div style={{ flexShrink: 0 }}>
                            <FunnelBar total={st.total} pending={st.pending} />
                          </div>

                          {/* Pending chip */}
                          <div style={{ width: 110, flexShrink: 0 }}>
                            {st.pending > 0 ? (
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                  fontSize: 12,
                                  fontWeight: 500,
                                  padding: '4px 10px',
                                  borderRadius: 8,
                                  background: '#FFF7ED',
                                  color: '#C2410C',
                                }}
                              >
                                ⏳ {st.pending} ждут
                              </span>
                            ) : (
                              <span style={{ fontSize: 12, color: '#D1D5DB' }}>нет ожидающих</span>
                            )}
                          </div>

                          {/* Arrow */}
                          <div style={{ flexShrink: 0, paddingRight: 16 }}>
                            <ArrowRight size={16} color="#C4C9D4" />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
      </div>

      {/* Modal */}
      {modalOpen && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 100, padding: 16,
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            style={{
              width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto',
              background: '#fff', borderRadius: 14, padding: 24,
              boxShadow: '0 12px 40px rgba(0,0,0,0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 17, fontWeight: 600, marginBottom: 18 }}>Новая вакансия</h2>

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Ссылка hh.ru</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, marginTop: 4 }}>
              <input
                value={hhUrl}
                onChange={(e) => setHhUrl(e.target.value)}
                placeholder="https://hh.ru/vacancy/…"
                style={{ ...inputStyle, marginBottom: 0, flex: 1 }}
              />
              <button
                type="button"
                onClick={parseHh}
                disabled={parsing}
                style={{
                  padding: '10px 14px', borderRadius: 8, border: '1px solid #E5E7EB',
                  background: '#F9FAFB', whiteSpace: 'nowrap', fontSize: 13, cursor: 'pointer',
                }}
              >
                {parsing ? 'Загрузка…' : 'Заполнить'}
              </button>
            </div>

            {hhFallbackOpen && (
              <div style={{
                marginBottom: 16, padding: 12, borderRadius: 8,
                background: '#FFF7ED', border: '1px solid #FED7AA', fontSize: 13,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Вставьте текст вакансии</div>
                <div style={{ color: '#6B7280', marginBottom: 8 }}>
                  Откройте вакансию на hh.ru, скопируйте текст целиком и вставьте сюда.
                </div>
                <textarea
                  value={hhPaste}
                  onChange={(e) => setHhPaste(e.target.value)}
                  rows={5}
                  placeholder="Скопируйте и вставьте текст вакансии…"
                  style={{ ...inputStyle, marginBottom: 8, resize: 'vertical', borderColor: '#FDBA74' }}
                />
                <button
                  type="button"
                  onClick={() => {
                    const parsed = parsePastedVacancyText(hhPaste)
                    if (!parsed.description && !parsed.requirements) { showToast('Вставьте текст вакансии', 'error'); return }
                    if (!requirements.trim() && parsed.requirements) setRequirements(parsed.requirements)
                    if (!description.trim() && parsed.description) setDescription(parsed.description)
                    showToast('Текст применён')
                    setHhFallbackOpen(false)
                  }}
                  style={{
                    padding: '9px 14px', borderRadius: 8, border: 'none',
                    background: '#F97316', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer',
                  }}
                >
                  Применить
                </button>
              </div>
            )}

            {preview && (
              <div style={{
                marginBottom: 16, padding: 12, borderRadius: 8,
                background: '#F9FAFB', border: '1px solid #F0F0F0', fontSize: 13,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Превью с hh.ru</div>
                <div>
                  <strong>{preview.title || '—'}</strong>
                  {preview.company && <span style={{ color: '#6B7280' }}> · {preview.company}</span>}
                </div>
                {preview.salary && <div style={{ color: '#6B7280', marginTop: 3 }}>{preview.salary}</div>}
                {preview.requirements && (
                  <p style={{ marginTop: 6, color: '#374151', maxHeight: 72, overflow: 'hidden' }}>
                    {preview.requirements.slice(0, 200)}{preview.requirements.length > 200 ? '…' : ''}
                  </p>
                )}
              </div>
            )}

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Название</label>
            <input placeholder="Frontend Developer" value={title} onChange={(e) => setTitle(e.target.value)} style={{ ...inputStyle, marginTop: 4 }} />

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Компания</label>
            <input placeholder="Название компании" value={company} onChange={(e) => setCompany(e.target.value)} style={{ ...inputStyle, marginTop: 4 }} />

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Требования</label>
            <textarea placeholder="Опыт, навыки, стек…" value={requirements} onChange={(e) => setRequirements(e.target.value)} rows={3} style={{ ...inputStyle, marginTop: 4, resize: 'vertical' }} />

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Описание</label>
            <textarea placeholder="Задачи, условия, команда…" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} style={{ ...inputStyle, marginTop: 4, resize: 'vertical' }} />

            <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Вводные для ИИ <span style={{ fontWeight: 400, color: '#C4C9D4' }}>(опционально)</span></label>
            <textarea placeholder="Особые критерии отбора для AI-скрининга…" value={aiScreeningPrompt} onChange={(e) => setAiScreeningPrompt(e.target.value)} rows={2} style={{ ...inputStyle, marginTop: 4, resize: 'vertical' }} />

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => { setModalOpen(false); resetModal() }}
                style={{
                  flex: 1, padding: 11, background: '#F3F4F6', color: '#374151',
                  border: 'none', borderRadius: 9, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={createVacancy}
                disabled={saving}
                style={{
                  flex: 2, padding: 11, background: '#4F46E5', color: '#fff',
                  border: 'none', borderRadius: 9, fontWeight: 500, cursor: 'pointer',
                }}
              >
                {saving ? 'Создание…' : 'Создать вакансию'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
