import {
  formatTextContent,
  isAnalysisContent,
  roleLabel,
  splitDialogEntries,
} from '../utils/dialogLog'

const sectionTitleStyle = {
  fontSize: 12,
  fontWeight: 600,
  color: '#6B7280',
  margin: '10px 0 6px',
  textTransform: 'uppercase',
  letterSpacing: '0.02em',
}

const listStyle = {
  margin: 0,
  paddingLeft: 18,
  fontSize: 13,
  color: '#374151',
  lineHeight: 1.5,
}

function AnalysisBlock({ data }) {
  const content =
    data?.content && typeof data.content === 'object' ? data.content : data?.legacy || data

  if (!content || typeof content !== 'object') return null

  const sections = [
    ['strengths', 'Сильные стороны', '#166534'],
    ['weaknesses', 'Слабые стороны', '#B45309'],
    ['red_flags', 'Красные флаги', '#B91C1C'],
    ['verification_questions', 'Вопросы для проверки', '#4F46E5'],
  ]

  return (
    <div
      style={{
        padding: 12,
        borderRadius: 8,
        background: '#F8FAFC',
        border: '1px solid #E5E7EB',
        marginBottom: 10,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: '#111827', marginBottom: 4 }}>
        Анализ резюме (ИИ)
      </div>
      {sections.map(([key, title, color]) => {
        const items = content[key]
        if (!Array.isArray(items) || items.length === 0) return null
        return (
          <div key={key}>
            <div style={{ ...sectionTitleStyle, color }}>{title}</div>
            <ul style={listStyle}>
              {items.map((item, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  {String(item)}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      {Array.isArray(content.red_flags) && content.red_flags.length === 0 && (
        <p style={{ fontSize: 12, color: '#9CA3AF', margin: '8px 0 0' }}>
          Красных флагов не выявлено
        </p>
      )}
    </div>
  )
}

function ChatBubble({ entry }) {
  const role = (entry.role || '').toLowerCase()
  const isBot = role === 'assistant'
  if (isAnalysisContent(entry.content)) return null

  const text = formatTextContent(entry.content)
  if (!text || text === '—') return null

  return (
    <div
      style={{
        marginBottom: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: isBot ? 'flex-start' : 'flex-end',
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: '#9CA3AF',
          marginBottom: 4,
        }}
      >
        {roleLabel(role)}
      </span>
      <div
        style={{
          maxWidth: '92%',
          padding: '10px 12px',
          borderRadius: isBot ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
          background: isBot ? '#EEF2FF' : '#F3F4F6',
          color: '#111827',
          fontSize: 13,
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
        }}
      >
        {text}
      </div>
    </div>
  )
}

/** @param {{ dialogLog: unknown, showAnalysis?: boolean }} props */
export default function DialogLogView({ dialogLog, showAnalysis = false }) {
  const { chat, analysis } = splitDialogEntries(dialogLog)

  const hasChat = chat.length > 0
  const hasAnalysis = showAnalysis && analysis.length > 0

  if (!hasChat && !hasAnalysis) return null

  return (
    <div style={{ padding: '12px 16px', borderTop: '1px solid #F0F0F0' }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, color: '#111827' }}>
        {hasChat ? 'Диалог с ботом' : 'Анализ резюме'}
      </div>

      {hasAnalysis &&
        analysis.map((entry, i) => <AnalysisBlock key={`analysis-${i}`} data={entry} />)}

      {hasChat &&
        chat.map((entry, i) => <ChatBubble key={`chat-${i}`} entry={entry} />)}
    </div>
  )
}
