export function candidateFullName(screening) {
  return (
    screening?.candidate?.full_name ||
    screening?.candidate_name ||
    'Кандидат'
  )
}

export function screeningVerdict(screening) {
  if (screening?.status === 'pending') return 'pending'
  if (screening?.status === 'failed') return 'failed'

  const v =
    screening?.display_verdict ??
    (screening?.status === 'rejected' ? 'rejected' : screening?.verdict)
  return (v || '').toLowerCase() || 'maybe'
}

export const nameTruncateStyle = {
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: 200,
}
