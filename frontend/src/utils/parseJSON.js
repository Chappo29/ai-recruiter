import { extractAnalysisFromDialog, normalizeDialogLog } from './dialogLog'

export function parseJSON(value, fallback = {}) {
  try {
    if (value == null) return fallback
    return typeof value === 'string' ? JSON.parse(value) : value
  } catch {
    return fallback
  }
}

export function screeningExtras(screening) {
  const dialogLog = normalizeDialogLog(screening.dialog_log)
  const aiMarkers = parseJSON(screening.ai_markers, {})
  const analysis = extractAnalysisFromDialog(dialogLog)
  return {
    dialogLog,
    aiMarkers,
    strengths: analysis.strengths,
    weaknesses: analysis.weaknesses,
    questions: analysis.questions,
    redFlags: analysis.redFlags,
  }
}
