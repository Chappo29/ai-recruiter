import { parseJSON } from './parseJSON'

const ANALYSIS_KEYS = [
  ['strengths', 'Сильные стороны'],
  ['weaknesses', 'Слабые стороны'],
  ['red_flags', 'Красные флаги'],
  ['verification_questions', 'Вопросы для проверки'],
]

export function normalizeDialogLog(raw) {
  const parsed = raw == null ? null : typeof raw === 'string' ? parseJSON(raw, null) : raw
  if (!parsed) return []
  if (Array.isArray(parsed)) return parsed
  if (typeof parsed === 'object' && Array.isArray(parsed.messages)) {
    return parsed.messages
  }
  if (typeof parsed === 'object') {
    return [{ role: 'ai_analysis', content: parsed }]
  }
  return []
}

export function extractAnalysisFromDialog(dialogLog) {
  const entries = normalizeDialogLog(dialogLog)
  const out = {
    strengths: [],
    weaknesses: [],
    redFlags: [],
    questions: [],
  }

  const apply = (obj) => {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return
    if (Array.isArray(obj.strengths)) out.strengths = obj.strengths
    if (Array.isArray(obj.weaknesses)) out.weaknesses = obj.weaknesses
    if (Array.isArray(obj.red_flags)) out.redFlags = obj.red_flags
    if (Array.isArray(obj.verification_questions)) {
      out.questions = obj.verification_questions
    }
  }

  for (const entry of entries) {
    if (entry?.role === 'ai_analysis') {
      apply(entry.content)
      continue
    }
    if (entry?.legacy) {
      apply(entry.legacy)
      continue
    }
    if (entry?.content && typeof entry.content === 'object' && !Array.isArray(entry.content)) {
      if (
        'strengths' in entry.content ||
        'weaknesses' in entry.content ||
        'verification_questions' in entry.content
      ) {
        apply(entry.content)
      }
    }
  }

  return out
}

export function roleLabel(role) {
  switch ((role || '').toLowerCase()) {
    case 'assistant':
      return 'Бот'
    case 'candidate':
      return 'Кандидат'
    case 'ai_analysis':
      return 'Анализ резюме'
    default:
      return 'Сообщение'
  }
}

export function isAnalysisContent(content) {
  if (!content || typeof content !== 'object' || Array.isArray(content)) return false
  return ANALYSIS_KEYS.some(([key]) => key in content)
}

export function formatTextContent(content) {
  if (content == null) return '—'
  if (typeof content === 'string') return content.trim() || '—'
  if (typeof content === 'number' || typeof content === 'boolean') {
    return String(content)
  }
  return null
}

export function splitDialogEntries(dialogLog) {
  const entries = normalizeDialogLog(dialogLog)
  const chat = []
  const analysis = []

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') continue
    const role = (entry.role || '').toLowerCase()
    if (role === 'ai_analysis' || isAnalysisContent(entry.content) || entry.legacy) {
      analysis.push(entry)
    } else if (role === 'assistant' || role === 'candidate') {
      chat.push(entry)
    } else {
      const text = formatTextContent(entry.content ?? entry.legacy ?? entry)
      if (text) chat.push({ ...entry, role: role || 'message', content: text })
    }
  }

  return { chat, analysis }
}
