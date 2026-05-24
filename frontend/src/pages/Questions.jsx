import { useCallback, useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Plus, Sparkles, Trash2 } from 'lucide-react'
import client from '../api/client'
import { PageTopbar } from '../components/Sidebar'
import { useToast } from '../components/Toast'

const cardStyle = {
  background: '#FFFFFF',
  border: '1px solid #F0F0F0',
  borderRadius: 12,
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  padding: 20,
  marginBottom: 16,
}

const inputStyle = {
  flex: 1,
  border: '1px solid #E5E7EB',
  borderRadius: 8,
  padding: '10px 14px',
  fontSize: 14,
}

export default function Questions() {
  const { showToast } = useToast()
  const [vacancies, setVacancies] = useState([])
  const [vacancyId, setVacancyId] = useState('')
  const [questions, setQuestions] = useState([])
  const [suggested, setSuggested] = useState([])
  const [newText, setNewText] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggesting, setSuggesting] = useState(false)

  useEffect(() => {
    client
      .get('/vacancies/')
      .then(({ data }) => {
        setVacancies(data)
        if (data.length > 0) setVacancyId(data[0].id)
      })
      .catch(() => showToast('Не удалось загрузить вакансии', 'error'))
  }, [])

  const loadQuestions = useCallback(() => {
    if (!vacancyId) return
    setLoading(true)
    client
      .get(`/questions/vacancy/${vacancyId}`)
      .then(({ data }) => setQuestions(data))
      .catch(() => {
        setQuestions([])
        showToast('Не удалось загрузить вопросы', 'error')
      })
      .finally(() => setLoading(false))
  }, [vacancyId, showToast])

  useEffect(() => {
    setSuggested([])
    loadQuestions()
  }, [loadQuestions])

  const addQuestion = async (text, orderIndex = questions.length) => {
    const trimmed = text.trim()
    if (!trimmed || !vacancyId) return
    try {
      const { data } = await client.post('/questions/', {
        vacancy_id: vacancyId,
        text: trimmed,
        order_index: orderIndex,
      })
      setQuestions((prev) =>
        [...prev, data].sort((a, b) => a.order_index - b.order_index)
      )
      showToast('Вопрос добавлен')
      return true
    } catch {
      showToast('Не удалось добавить вопрос', 'error')
      return false
    }
  }

  const handleAddNew = async () => {
    if (!newText.trim()) return
    const ok = await addQuestion(newText)
    if (ok) setNewText('')
  }

  const handleDelete = async (id) => {
    try {
      await client.delete(`/questions/${id}`)
      setQuestions((prev) => prev.filter((q) => q.id !== id))
      showToast('Вопрос удалён')
    } catch {
      showToast('Не удалось удалить', 'error')
    }
  }

  const moveQuestion = async (index, direction) => {
    const target = index + direction
    if (target < 0 || target >= questions.length) return

    const reordered = [...questions]
    const [item] = reordered.splice(index, 1)
    reordered.splice(target, 0, item)

    const withOrder = reordered.map((q, i) => ({ ...q, order_index: i }))
    setQuestions(withOrder)

    try {
      await Promise.all(
        withOrder.map((q) =>
          client.put(`/questions/${q.id}`, { order_index: q.order_index })
        )
      )
    } catch {
      showToast('Не удалось сохранить порядок', 'error')
      loadQuestions()
    }
  }

  const handleSuggest = async () => {
    if (!vacancyId) return
    setSuggesting(true)
    try {
      const { data } = await client.post('/questions/ai-suggest', {
        vacancy_id: vacancyId,
      })
      const existing = new Set(questions.map((q) => q.text.toLowerCase()))
      const fresh = (data.questions || []).filter(
        (t) => t && !existing.has(t.toLowerCase())
      )
      setSuggested(fresh)
      if (!fresh.length) showToast('Новых предложений нет')
    } catch {
      showToast('Не удалось сгенерировать вопросы', 'error')
    } finally {
      setSuggesting(false)
    }
  }

  const addFromSuggested = async (text, index) => {
    const ok = await addQuestion(text)
    if (ok) setSuggested((prev) => prev.filter((_, i) => i !== index))
  }

  const selectedVacancy = vacancies.find((v) => String(v.id) === String(vacancyId))

  return (
    <div>
      <PageTopbar
        title="Вопросы для кандидатов"
        subtitle={selectedVacancy?.title || 'Выберите вакансию'}
      />

      <div style={{ padding: 24, maxWidth: 720 }}>
        <select
          value={vacancyId}
          onChange={(e) => setVacancyId(e.target.value)}
          style={{
            width: '100%',
            maxWidth: 420,
            marginBottom: 24,
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid #E5E7EB',
            fontSize: 14,
            background: '#FFFFFF',
          }}
        >
          {vacancies.map((v) => (
            <option key={v.id} value={v.id}>
              {v.title}
            </option>
          ))}
        </select>

        {vacancyId && (
          <>
            <section style={cardStyle}>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>
                Ваши вопросы
              </h2>

              {loading && (
                <p style={{ fontSize: 13, color: '#9CA3AF' }}>Загрузка…</p>
              )}

              {!loading && questions.length === 0 && (
                <p style={{ fontSize: 13, color: '#9CA3AF', marginBottom: 16 }}>
                  Пока нет вопросов. Добавьте вручную или сгенерируйте с помощью ИИ.
                </p>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {questions.map((q, index) => (
                  <div
                    key={q.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid #F0F0F0',
                      background: '#F9FAFB',
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <button
                        type="button"
                        onClick={() => moveQuestion(index, -1)}
                        disabled={index === 0}
                        style={{
                          border: 'none',
                          background: 'transparent',
                          padding: 2,
                          opacity: index === 0 ? 0.3 : 1,
                        }}
                        title="Вверх"
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveQuestion(index, 1)}
                        disabled={index === questions.length - 1}
                        style={{
                          border: 'none',
                          background: 'transparent',
                          padding: 2,
                          opacity: index === questions.length - 1 ? 0.3 : 1,
                        }}
                        title="Вниз"
                      >
                        <ArrowDown size={14} />
                      </button>
                    </div>
                    <span style={{ flex: 1, fontSize: 14, color: '#374151' }}>
                      {q.text}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDelete(q.id)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        color: '#9F1239',
                        padding: 6,
                      }}
                      title="Удалить"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <input
                  type="text"
                  placeholder="Добавить вопрос"
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddNew()}
                  style={inputStyle}
                />
                <button
                  type="button"
                  onClick={handleAddNew}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 8,
                    border: 'none',
                    background: '#4F46E5',
                    color: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <Plus size={18} />
                </button>
              </div>
            </section>

            <section style={cardStyle}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 16,
                  flexWrap: 'wrap',
                  gap: 8,
                }}
              >
                <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
                  Предложено ИИ
                </h2>
                <button
                  type="button"
                  onClick={handleSuggest}
                  disabled={suggesting}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    borderRadius: 8,
                    border: '1px solid #E5E7EB',
                    background: '#FFFFFF',
                    fontSize: 13,
                    color: '#4F46E5',
                  }}
                >
                  <Sparkles size={16} />
                  {suggesting ? 'Генерация…' : 'Сгенерировать вопросы'}
                </button>
              </div>

              {suggested.length === 0 && (
                <p style={{ fontSize: 13, color: '#9CA3AF' }}>
                  Нажмите «Сгенерировать вопросы», чтобы получить предложения на основе
                  вакансии.
                </p>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {suggested.map((text, index) => (
                  <div
                    key={`${index}-${text.slice(0, 20)}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid #EEF2FF',
                      background: '#F5F3FF',
                    }}
                  >
                    <span style={{ flex: 1, fontSize: 14, color: '#374151' }}>
                      {text}
                    </span>
                    <button
                      type="button"
                      onClick={() => addFromSuggested(text, index)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 6,
                        border: 'none',
                        background: '#4F46E5',
                        color: '#FFFFFF',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                      title="Добавить"
                    >
                      <Plus size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
