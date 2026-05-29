import { isAiAnalysisPending } from './screeningAnalysis'

export const PIPELINE_STAGES = [
  {
    key: 'new',
    title: 'Новые',
    description: 'Свежие отклики, ожидают AI-анализа',
    color: '#6B7280',
  },
  {
    key: 'scoring',
    title: 'Оценка...',
    description: 'AI анализирует резюме и проводит интервью',
    color: '#F59E0B',
  },
  {
    key: 'ai_screened',
    title: 'AI проверил',
    description: 'Прошли автоматический скрининг',
    color: '#4F46E5',
  },
  {
    key: 'interview',
    title: 'Собеседование',
    description: 'Переданы HR или менеджеру',
    color: '#22C55E',
  },
  {
    key: 'rejected',
    title: 'Отклонено',
    description: 'Не подошли по требованиям',
    color: '#DC2626',
    hiddenByDefault: true,
  },
]

/**
 * Определяет стадию кандидата в воронке
 * @param {Object} screening - объект screening
 * @returns {string} - ключ стадии: 'new' | 'ai_screened' | 'interview' | 'rejected'
 */
export function getScreeningStage(screening) {
  if (!screening) return 'new'

  if (screening.status === 'rejected') {
    return 'rejected'
  }

  if (screening.status === 'forwarded') {
    return 'interview'
  }

  // "scoring": резюме разбирается LLM или идёт интервью с ботом —
  // финальный балл ещё не сформирован.
  if (screening.status === 'scoring') {
    return 'scoring'
  }

  const hasAiAnalysis = screening.score != null && !isAiAnalysisPending(screening)
  return hasAiAnalysis ? 'ai_screened' : 'new'
}

/**
 * Группирует screenings по стадиям
 * @param {Array} screenings - массив screenings
 * @param {boolean} showRejected - показывать ли отклоненных
 * @returns {Object} - объект { new: [...], ai_screened: [...], interview: [...], rejected: [...] }
 */
export function groupScreeningsByStage(screenings, showRejected = false) {
  const grouped = {
    new: [],
    scoring: [],
    ai_screened: [],
    interview: [],
    rejected: [],
  }
  
  screenings.forEach((screening) => {
    const stage = getScreeningStage(screening)
    if (stage === 'rejected' && !showRejected) {
      return // Пропускаем отклоненных, если не нужно показывать
    }
    grouped[stage].push(screening)
  })
  
  return grouped
}

/**
 * Получает объект стадии по ключу
 * @param {string} stageKey - ключ стадии
 * @returns {Object} - объект стадии
 */
export function getStageConfig(stageKey) {
  return PIPELINE_STAGES.find((s) => s.key === stageKey) || PIPELINE_STAGES[0]
}
