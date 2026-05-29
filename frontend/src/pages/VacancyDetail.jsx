import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Archive,
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronUp,
  Edit2,
  FileText,
  HelpCircle,
  MoreHorizontal,
  Save,
  Trash2,
  Users,
  X,
} from 'lucide-react'
import client from '../api/client'
import KanbanBoard from '../components/KanbanBoard'
import { PageTopbar } from '../components/Sidebar'
import { CandidateCardSkeleton } from '../components/Skeleton'
import { useToast } from '../components/Toast'
import { isAiAnalysisPending } from '../utils/screeningAnalysis'

// ─── helpers ────────────────────────────────────────────────────────────────

const RUBRIC_TITLE_FALLBACK = {
  hard_skills: 'Проф. навыки',
  soft_skills: 'Мягкие навыки',
}

function rubricTitle(c) {
  const raw = (c?.title || '').trim()
  if (raw) return raw
  const id = (c?.id || '').trim()
  return RUBRIC_TITLE_FALLBACK[id] || id || '—'
}

function HelpTip({ text }) {
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <span
        tabIndex={0}
        aria-label={text}
        style={{ display: 'inline-flex', alignItems: 'center', color: '#9CA3AF', cursor: 'help' }}
      >
        <HelpCircle size={14} />
      </span>
      <span
        className="helptip-popup"
        style={{
          position: 'absolute',
          top: '50%',
          left: '100%',
          transform: 'translate(8px, -50%)',
          background: '#111827',
          color: '#F9FAFB',
          padding: '8px 10px',
          borderRadius: 8,
          fontSize: 12,
          width: 260,
          lineHeight: 1.4,
          boxShadow: '0 8px 18px rgba(0,0,0,0.18)',
          opacity: 0,
          pointerEvents: 'none',
          zIndex: 50,
          visibility: 'hidden',
          transition: 'opacity 120ms',
        }}
      >
        {text}
      </span>
      <style>{`
        span:hover > .helptip-popup,
        span:focus-within > .helptip-popup { visibility: visible; opacity: 1 !important; }
      `}</style>
    </span>
  )
}

// ─── Funnel bar ──────────────────────────────────────────────────────────────

const FUNNEL_STAGES = [
  { key: 'total', label: 'Всего', color: '#6366F1', bg: '#EEF2FF' },
  { key: 'pending', label: 'На рассмотрении', color: '#F59E0B', bg: '#FFF7ED' },
  { key: 'forwarded', label: 'Передан дальше', color: '#22C55E', bg: '#F0FDF4' },
  { key: 'rejected', label: 'Отказ', color: '#EF4444', bg: '#FFF1F2' },
]

function FunnelStats({ stats }) {
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      {FUNNEL_STAGES.map(({ key, label, color, bg }) => (
        <div
          key={key}
          style={{
            flex: '1 1 120px',
            background: bg,
            borderRadius: 12,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <span style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
            {stats[key] ?? 0}
          </span>
          <span style={{ fontSize: 12, color: '#6B7280' }}>{label}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Collapsible text block ──────────────────────────────────────────────────

function TextBlock({ label, value, onSave, placeholder = '—' }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const lines = (value || '').split('\n')
  const COLLAPSE_LINES = 5
  const long = lines.length > COLLAPSE_LINES || (value || '').length > 400
  const displayText =
    !expanded && long
      ? lines.slice(0, COLLAPSE_LINES).join('\n') + '…'
      : value || ''

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(draft)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>{label}</span>
        {!editing && (
          <button
            type="button"
            onClick={() => { setDraft(value || ''); setEditing(true) }}
            style={{ border: 'none', background: 'transparent', color: '#9CA3AF', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}
          >
            <Edit2 size={13} /> Изменить
          </button>
        )}
      </div>

      {editing ? (
        <div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={8}
            style={{
              width: '100%',
              border: '1px solid #C7D2FE',
              borderRadius: 8,
              padding: '10px 12px',
              fontSize: 13,
              lineHeight: 1.6,
              resize: 'vertical',
              outline: 'none',
              marginBottom: 8,
              boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => setEditing(false)}
              style={{ padding: '7px 14px', borderRadius: 7, border: '1px solid #E5E7EB', background: '#F9FAFB', fontSize: 13, cursor: 'pointer' }}
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 7, border: 'none', background: '#4F46E5', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
            >
              <Save size={13} /> {saving ? 'Сохранение…' : 'Сохранить'}
            </button>
          </div>
        </div>
      ) : (
        <div>
          {value ? (
            <>
              <p style={{ fontSize: 13, color: '#374151', whiteSpace: 'pre-wrap', lineHeight: 1.6, margin: 0 }}>
                {displayText}
              </p>
              {long && (
                <button
                  type="button"
                  onClick={() => setExpanded(!expanded)}
                  style={{ marginTop: 6, border: 'none', background: 'transparent', color: '#4F46E5', fontSize: 12, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
                >
                  {expanded ? <><ChevronUp size={13} /> Свернуть</> : <><ChevronDown size={13} /> Показать полностью</>}
                </button>
              )}
            </>
          ) : (
            <p style={{ fontSize: 13, color: '#C4C9D4', margin: 0 }}>{placeholder}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Tab pill ────────────────────────────────────────────────────────────────

function Tab({ label, badge, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '8px 16px',
        border: 'none',
        borderBottom: active ? '2px solid #4F46E5' : '2px solid transparent',
        background: 'transparent',
        color: active ? '#4F46E5' : '#6B7280',
        fontSize: 14,
        fontWeight: active ? 600 : 400,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        transition: 'all 0.15s',
      }}
    >
      {label}
      {badge != null && (
        <span
          style={{
            background: active ? '#EEF2FF' : '#F3F4F6',
            color: active ? '#4F46E5' : '#9CA3AF',
            fontSize: 11,
            fontWeight: 600,
            padding: '1px 7px',
            borderRadius: 999,
          }}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

// ─── Rubric editor (full) ────────────────────────────────────────────────────

function RubricEditor({ id, rubricOverview, onReload, showToast }) {
  const [rubricLoading, setRubricLoading] = useState(false)
  const [rubricSaving, setRubricSaving] = useState(false)
  const [localOverview, setLocalOverview] = useState(rubricOverview)

  useEffect(() => { setLocalOverview(rubricOverview) }, [rubricOverview])

  const draftRubric = localOverview?.draft
  const approvedRubric = localOverview?.approved

  const updateCompetency = (index, field, value) => {
    if (!draftRubric?.rubric_json?.competencies) return
    const next = draftRubric.rubric_json.competencies.map((c, i) =>
      i === index ? { ...c, [field]: value } : c
    )
    setLocalOverview((prev) => ({
      ...prev,
      draft: { ...prev.draft, rubric_json: { ...prev.draft.rubric_json, competencies: next } },
    }))
  }

  const addCompetency = () => {
    const competencies = draftRubric?.rubric_json?.competencies || []
    setLocalOverview((prev) => ({
      ...prev,
      draft: {
        ...(prev.draft || { rubric_json: {} }),
        rubric_json: {
          ...(prev.draft?.rubric_json || {}),
          competencies: [...competencies, { id: `c_${Date.now()}`, title: '', weight: 0.1, must_have: false }],
        },
      },
    }))
  }

  const removeCompetency = (index) => {
    const next = draftRubric.rubric_json.competencies.filter((_, i) => i !== index)
    setLocalOverview((prev) => ({
      ...prev,
      draft: { ...prev.draft, rubric_json: { ...prev.draft.rubric_json, competencies: next } },
    }))
  }

  const generateRubric = async () => {
    setRubricLoading(true)
    try {
      await client.post(`/vacancies/${id}/rubric/generate`, null, { timeout: 60000 })
      await onReload()
      showToast('Черновик рубрики создан')
    } catch {
      showToast('Не удалось сгенерировать рубрику', 'error')
    } finally {
      setRubricLoading(false)
    }
  }

  const saveDraft = async () => {
    if (!draftRubric?.id) return
    setRubricSaving(true)
    try {
      await client.put(`/vacancies/${id}/rubric/${draftRubric.id}`, {
        rubric_json: {
          competencies: draftRubric.rubric_json.competencies,
          generated_from: draftRubric.rubric_json.generated_from || {},
        },
      })
      await onReload()
      showToast('Рубрика сохранена')
    } catch {
      showToast('Не удалось сохранить', 'error')
    } finally {
      setRubricSaving(false)
    }
  }

  const approveRubric = async () => {
    if (!draftRubric?.id) return
    setRubricSaving(true)
    try {
      await client.post(`/vacancies/${id}/rubric/${draftRubric.id}/approve`)
      await onReload()
      showToast('Рубрика утверждена')
    } catch {
      showToast('Не удалось утвердить', 'error')
    } finally {
      setRubricSaving(false)
    }
  }

  const competencies = draftRubric?.rubric_json?.competencies || []
  const weightTotal = Math.round(competencies.reduce((s, c) => s + (c.weight || 0) * 100, 0))
  const weightOk = weightTotal >= 99 && weightTotal <= 101

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Status row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        {approvedRubric && !draftRubric && (
          <span style={{ fontSize: 12, padding: '3px 10px', borderRadius: 999, background: '#F0FDF4', color: '#15803D', fontWeight: 500 }}>
            ✓ Утверждена v{approvedRubric.version}
          </span>
        )}
        {draftRubric && (
          <span style={{ fontSize: 12, padding: '3px 10px', borderRadius: 999, background: '#FFF7ED', color: '#B45309', fontWeight: 500 }}>
            Черновик v{draftRubric.version}
          </span>
        )}
        {approvedRubric && draftRubric && (
          <span style={{ fontSize: 12, color: '#6B7280' }}>
            Активная: v{approvedRubric.version}
          </span>
        )}
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={generateRubric}
          disabled={rubricLoading}
          style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #E5E7EB', background: '#fff', fontSize: 13, cursor: 'pointer' }}
        >
          {rubricLoading ? 'Генерация…' : draftRubric || approvedRubric ? 'Перегенерировать' : 'Сгенерировать из описания'}
        </button>
      </div>

      {/* Competency table */}
      {draftRubric ? (
        <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, overflow: 'hidden' }}>
          {/* Header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 90px 130px 36px',
            gap: 8,
            padding: '10px 16px',
            background: '#F9FAFB',
            borderBottom: '1px solid #F0F0F0',
            fontSize: 12,
            fontWeight: 600,
            color: '#6B7280',
          }}>
            <div>Компетенция</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              Вес, % <HelpTip text="Вклад в итоговую оценку. Сумма должна быть 100%." />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              Обязательно <HelpTip text="Провал обязательной компетенции = не рекомендован, даже при высоком балле." />
            </div>
            <div />
          </div>

          {competencies.map((c, index) => (
            <div
              key={c.id || index}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 90px 130px 36px',
                gap: 8,
                padding: '10px 16px',
                borderTop: '1px solid #F5F5F5',
                alignItems: 'center',
              }}
            >
              <input
                value={c.title ?? rubricTitle(c)}
                onChange={(e) => updateCompetency(index, 'title', e.target.value)}
                placeholder="Название компетенции"
                style={{ border: '1px solid #E5E7EB', borderRadius: 6, padding: '6px 8px', fontSize: 13, width: '100%', boxSizing: 'border-box' }}
              />
              <input
                type="number"
                min={0}
                max={100}
                value={Math.round((c.weight || 0) * 100)}
                onChange={(e) => updateCompetency(index, 'weight', Number(e.target.value) / 100)}
                style={{ border: '1px solid #E5E7EB', borderRadius: 6, padding: '6px 8px', fontSize: 13, width: '100%', boxSizing: 'border-box' }}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', userSelect: 'none' }}>
                <input
                  type="checkbox"
                  checked={Boolean(c.must_have)}
                  onChange={(e) => updateCompetency(index, 'must_have', e.target.checked)}
                />
                Must-have
              </label>
              <button
                type="button"
                onClick={() => removeCompetency(index)}
                style={{ border: 'none', background: 'transparent', color: '#D1D5DB', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}
              >
                <X size={15} />
              </button>
            </div>
          ))}

          {/* Add row */}
          <div style={{ padding: '10px 16px', borderTop: '1px solid #F5F5F5' }}>
            <button
              type="button"
              onClick={addCompetency}
              style={{ border: 'none', background: 'transparent', color: '#4F46E5', fontSize: 13, fontWeight: 500, cursor: 'pointer', padding: 0 }}
            >
              + Добавить компетенцию
            </button>
          </div>

          {/* Weight total */}
          <div style={{ padding: '8px 16px', borderTop: '1px solid #F5F5F5', background: '#FAFAFA', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: weightOk ? '#15803D' : '#B45309' }}>
              Итого: {weightTotal}% {weightOk ? '✓' : '⚠️ должно быть 100%'}
            </span>
          </div>
        </div>
      ) : approvedRubric?.rubric_json?.competencies?.length > 0 ? (
        <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, overflow: 'hidden' }}>
          {approvedRubric.rubric_json.competencies.map((c, i) => (
            <div
              key={c.id || i}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '11px 16px',
                borderTop: i > 0 ? '1px solid #F5F5F5' : 'none',
                fontSize: 13,
              }}
            >
              <span style={{ color: '#111827' }}>{rubricTitle(c)}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {c.must_have && (
                  <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 999, background: '#FEF3C7', color: '#B45309', fontWeight: 500 }}>
                    обязательно
                  </span>
                )}
                <span style={{ fontSize: 13, fontWeight: 600, color: '#6B7280' }}>
                  {Math.round((c.weight || 0) * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ padding: '24px', textAlign: 'center', color: '#9CA3AF', fontSize: 13, background: '#F9FAFB', borderRadius: 12, border: '1px dashed #E5E7EB' }}>
          Рубрика не создана. Нажмите «Сгенерировать из описания» — ИИ подготовит компетенции.
        </div>
      )}

      {/* Actions */}
      {draftRubric && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={saveDraft}
            disabled={rubricSaving}
            style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #E5E7EB', background: '#fff', fontSize: 13, cursor: 'pointer' }}
          >
            {rubricSaving ? 'Сохранение…' : 'Сохранить черновик'}
          </button>
          <button
            type="button"
            onClick={approveRubric}
            disabled={rubricSaving || !weightOk}
            style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: weightOk ? '#4F46E5' : '#E5E7EB', color: weightOk ? '#fff' : '#9CA3AF', fontSize: 13, fontWeight: 500, cursor: weightOk ? 'pointer' : 'not-allowed' }}
          >
            Утвердить рубрику
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Dots menu ───────────────────────────────────────────────────────────────

function DotsMenu({ onDelete }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        style={{ padding: '8px 10px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
      >
        <MoreHorizontal size={16} color="#6B7280" />
      </button>
      {open && (
        <div style={{
          position: 'absolute',
          top: '110%',
          right: 0,
          background: '#fff',
          border: '1px solid #E5E7EB',
          borderRadius: 10,
          boxShadow: '0 8px 24px rgba(0,0,0,0.10)',
          minWidth: 160,
          zIndex: 100,
          overflow: 'hidden',
        }}>
          <button
            type="button"
            onClick={() => { setOpen(false); onDelete() }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 14px',
              border: 'none',
              background: 'transparent',
              color: '#DC2626',
              fontSize: 13,
              cursor: 'pointer',
              textAlign: 'left',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#FFF1F2' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
          >
            <Trash2 size={14} /> Удалить вакансию
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function VacancyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [vacancy, setVacancy] = useState(null)
  const [stats, setStats] = useState({ pending: 0, forwarded: 0, rejected: 0, total: 0 })
  const [screenings, setScreenings] = useState([])
  const [loading, setLoading] = useState(true)
  const [aiPrompt, setAiPrompt] = useState('')
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [rubricOverview, setRubricOverview] = useState({ draft: null, approved: null })
  const [activeTab, setActiveTab] = useState('overview')

  const loadRubric = useCallback(async () => {
    if (!id) return
    try {
      const { data } = await client.get(`/vacancies/${id}/rubric`)
      setRubricOverview(data || { draft: null, approved: null })
    } catch {
      setRubricOverview({ draft: null, approved: null })
    }
  }, [id])

  const refreshScreenings = useCallback(async () => {
    if (!id) return
    try {
      const [statsRes, scrRes] = await Promise.all([
        client.get(`/vacancies/${id}/stats`),
        client.get(`/screenings/vacancy/${id}`),
      ])
      setStats(statsRes.data)
      setScreenings(scrRes.data || [])
    } catch { /* silent refresh */ }
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
      await loadRubric()
    } catch {
      showToast('Не удалось загрузить вакансию', 'error')
      navigate('/vacancies')
    } finally {
      setLoading(false)
    }
  }, [id, navigate, showToast, loadRubric])

  useEffect(() => { load() }, [load])

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

  const patchVacancy = async (fields) => {
    await client.patch(`/vacancies/${id}`, fields)
    setVacancy((prev) => ({ ...prev, ...fields }))
    showToast('Сохранено')
  }

  const savePrompt = async () => {
    setSavingPrompt(true)
    try {
      await client.patch(`/vacancies/${id}`, { ai_screening_prompt: aiPrompt || null })
      showToast('Вводные для ИИ сохранены')
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
    if (!window.confirm('Вы уверены? Вакансия и все отклики будут удалены безвозвратно.')) return
    try {
      await client.delete(`/vacancies/${id}`)
      showToast('Вакансия удалена')
      navigate('/vacancies')
    } catch {
      showToast('Ошибка удаления', 'error')
    }
  }

  if (loading || !vacancy) {
    return <div style={{ padding: 24 }}><CandidateCardSkeleton /></div>
  }

  const isArchived = vacancy.status === 'archived'
  const statsTotal = stats.total ?? (stats.pending + stats.forwarded + stats.rejected)
  const statsWithTotal = { ...stats, total: statsTotal }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {/* Topbar */}
      <PageTopbar
        title={vacancy.title}
        subtitle={`${vacancy.company}${isArchived ? ' · Архив' : ''}`}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={() => navigate('/vacancies')}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#fff', fontSize: 13, cursor: 'pointer' }}
          >
            <ArrowLeft size={15} /> Назад
          </button>
          {!isArchived && (
            <button
              type="button"
              onClick={archiveVacancy}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#fff', fontSize: 13, cursor: 'pointer' }}
            >
              <Archive size={15} /> В архив
            </button>
          )}
          <DotsMenu onDelete={deleteVacancy} />
        </div>
      </PageTopbar>

      {/* Tabs */}
      <div style={{ background: '#fff', borderBottom: '1px solid #F0F0F0', padding: '0 24px', display: 'flex', gap: 0 }}>
        <Tab label="Обзор" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} />
        <Tab
          label="Кандидаты"
          badge={statsTotal > 0 ? statsTotal : null}
          active={activeTab === 'candidates'}
          onClick={() => setActiveTab('candidates')}
        />
        <Tab
          label="ИИ и рубрика"
          active={activeTab === 'ai'}
          onClick={() => setActiveTab('ai')}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: 24 }}>

        {/* ── Overview ── */}
        {activeTab === 'overview' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20, alignItems: 'start' }}>

            {/* Left column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Funnel stats */}
              <FunnelStats stats={statsWithTotal} />

              {/* Description */}
              <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 20 }}>
                <TextBlock
                  label="Описание"
                  value={vacancy.description}
                  placeholder="Описание не заполнено"
                  onSave={(v) => patchVacancy({ description: v || null })}
                />
                {vacancy.hh_url && (
                  <a
                    href={vacancy.hh_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 10, fontSize: 12, color: '#9CA3AF', textDecoration: 'none' }}
                  >
                    <FileText size={12} /> Открыть на hh.ru
                  </a>
                )}
              </div>

              {/* Requirements */}
              <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 20 }}>
                <TextBlock
                  label="Требования"
                  value={vacancy.requirements}
                  placeholder="Требования не заполнены"
                  onSave={(v) => patchVacancy({ requirements: v || null })}
                />
              </div>
            </div>

            {/* Right sidebar */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 16 }}>

              {/* AI prompt */}
              <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <Bot size={15} color="#6366F1" />
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Вводные для ИИ</span>
                </div>
                <textarea
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  rows={4}
                  placeholder="На что обратить внимание при отборе…"
                  style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 8, padding: '9px 11px', fontSize: 13, resize: 'none', outline: 'none', boxSizing: 'border-box', lineHeight: 1.5 }}
                />
                <button
                  type="button"
                  onClick={savePrompt}
                  disabled={savingPrompt}
                  style={{ marginTop: 8, width: '100%', padding: '8px', background: '#4F46E5', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
                >
                  {savingPrompt ? 'Сохранение…' : 'Сохранить'}
                </button>
              </div>

              {/* Rubric summary */}
              <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Рубрика оценки</span>
                  {rubricOverview.approved && (
                    <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: '#F0FDF4', color: '#15803D', fontWeight: 500 }}>
                      ✓ v{rubricOverview.approved.version}
                    </span>
                  )}
                </div>

                {(rubricOverview.approved || rubricOverview.draft) ? (() => {
                  const r = rubricOverview.approved || rubricOverview.draft
                  const comps = r?.rubric_json?.competencies || []
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {comps.slice(0, 4).map((c, i) => (
                        <div key={c.id || i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
                          <span style={{ color: '#374151', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {rubricTitle(c)}
                          </span>
                          <span style={{ color: '#6B7280', fontWeight: 600, flexShrink: 0, marginLeft: 8 }}>
                            {Math.round((c.weight || 0) * 100)}%
                          </span>
                        </div>
                      ))}
                      {comps.length > 4 && (
                        <span style={{ fontSize: 11, color: '#9CA3AF' }}>+{comps.length - 4} ещё</span>
                      )}
                    </div>
                  )
                })() : (
                  <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>Рубрика не создана</p>
                )}

                <button
                  type="button"
                  onClick={() => setActiveTab('ai')}
                  style={{ marginTop: 12, width: '100%', padding: '7px', background: '#F3F4F6', color: '#374151', border: 'none', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}
                >
                  {rubricOverview.approved || rubricOverview.draft ? 'Редактировать рубрику →' : 'Создать рубрику →'}
                </button>
              </div>

              {/* Quick link to candidates page */}
              <button
                type="button"
                onClick={() => setActiveTab('candidates')}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px', background: '#EEF2FF', color: '#4F46E5', border: 'none', borderRadius: 12, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
              >
                <Users size={15} /> Смотреть кандидатов ({statsTotal})
              </button>
            </div>
          </div>
        )}

        {/* ── Candidates ── */}
        {activeTab === 'candidates' && (
          <div>
            {screenings.length === 0 ? (
              <div style={{ padding: '60px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
                Пока нет откликов по этой вакансии
              </div>
            ) : (
              <KanbanBoard
                screenings={screenings}
                vacancyTitle={vacancy.title}
                onStatusChange={handleStatusChange}
              />
            )}
          </div>
        )}

        {/* ── AI + Rubric ── */}
        {activeTab === 'ai' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>

            {/* AI prompt */}
            <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Bot size={16} color="#6366F1" />
                <span style={{ fontSize: 15, fontWeight: 600, color: '#111827' }}>Вводные для ИИ</span>
              </div>
              <p style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 12, lineHeight: 1.5 }}>
                ИИ-скринер будет учитывать эти вводные при анализе резюме и ведении диалога с кандидатом.
              </p>
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                rows={8}
                placeholder="Например: обращай внимание на опыт B2B-продаж и работу с CRM. Не рассматривай без высшего образования."
                style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 8, padding: '10px 12px', fontSize: 13, resize: 'vertical', outline: 'none', boxSizing: 'border-box', lineHeight: 1.6 }}
              />
              <button
                type="button"
                onClick={savePrompt}
                disabled={savingPrompt}
                style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px', background: '#4F46E5', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
              >
                <Save size={14} /> {savingPrompt ? 'Сохранение…' : 'Сохранить вводные'}
              </button>
            </div>

            {/* Rubric */}
            <div style={{ background: '#fff', border: '1px solid #EBEBEB', borderRadius: 12, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#111827' }}>Рубрика оценки</span>
              </div>
              <p style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 16, lineHeight: 1.5 }}>
                Компетенции с весами используются для взвешенной оценки кандидатов. Нужно утвердить перед использованием.
              </p>
              <RubricEditor
                id={id}
                rubricOverview={rubricOverview}
                onReload={loadRubric}
                showToast={showToast}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
