/** Полное имя для веб-интерфейса (имя + фамилия). */
export function candidateFullName(screening) {
  return (
    screening?.candidate?.full_name ||
    screening?.candidate_name ||
    screening?.candidate?.first_name ||
    'Кандидат'
  )
}

/** Только имя — для подписей в Telegram-стиле, если понадобится. */
export function candidateFirstName(screening) {
  return (
    screening?.candidate?.first_name ||
    screening?.candidate?.full_name?.split(/\s+/)[0] ||
    screening?.candidate_name?.split(/\s+/)[0] ||
    'Кандидат'
  )
}

const HR_STATUSES = new Set(['pending', 'forwarded', 'rejected'])

/** HR-статус воронки (не путать с ИИ-verdict fit/maybe/reject). */
export function screeningHrStatus(screening) {
  const st = (screening?.status || '').toLowerCase()
  if (HR_STATUSES.has(st)) return st
  return 'pending'
}

export function screeningVerdict(screening) {
  const hr = screeningHrStatus(screening)
  if (HR_STATUSES.has(hr)) return hr
  const v = (screening?.verdict || '').toLowerCase()
  if (v === 'fit' || v === 'maybe' || v === 'reject') return v
  return 'pending'
}

export const nameTruncateStyle = {
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: 200,
}
