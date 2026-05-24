export function parseJSON(value, fallback = {}) {
  try {
    if (value == null) return fallback
    return typeof value === 'string' ? JSON.parse(value) : value
  } catch {
    return fallback
  }
}

export function screeningExtras(screening) {
  const dialogLog = parseJSON(screening.dialog_log, {})
  const aiMarkers = parseJSON(screening.ai_markers, {})
  return {
    dialogLog,
    aiMarkers,
    strengths: dialogLog.strengths || [],
    weaknesses: dialogLog.weaknesses || [],
    questions: dialogLog.verification_questions || [],
    redFlags: dialogLog.red_flags || [],
  }
}
