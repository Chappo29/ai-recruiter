const ANALYSIS_WAIT_MS = 3 * 60 * 1000

function screeningAgeMs(screening) {
  if (!screening?.created_at) return ANALYSIS_WAIT_MS + 1
  return Date.now() - new Date(screening.created_at).getTime()
}

/** ИИ ещё анализирует резюме (недавно создан, нет score и summary). */
export function isAiAnalysisPending(screening) {
  if (screening?.score != null) return false
  if ((screening?.summary || '').trim()) return false
  return screeningAgeMs(screening) < ANALYSIS_WAIT_MS
}

/** Анализ не дал score: ошибка, таймаут фоновой задачи или старая запись. */
export function isAiAnalysisMissing(screening) {
  if (screening?.score != null) return false
  if ((screening?.summary || '').trim()) return true
  return screeningAgeMs(screening) >= ANALYSIS_WAIT_MS
}
