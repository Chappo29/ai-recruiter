import { useState } from 'react'

import {

  AlertTriangle,

  Bot,

  CheckCircle,

  ChevronDown,

  ChevronUp,

  Download,

  ExternalLink,

  FileText,

  Mail,

  X,

} from 'lucide-react'

import client, { mediaUrl } from '../api/client'

import {
  candidateFullName,
  nameTruncateStyle,
  screeningHrStatus,
  screeningVerdict,
} from '../utils/candidate'

import { screeningExtras } from '../utils/parseJSON'
import {
  isAiAnalysisMissing,
  isAiAnalysisPending,
} from '../utils/screeningAnalysis'

import { useToast } from './Toast'

import Avatar from './Avatar'

import ScoreBar from './ScoreBar'

import DialogLogView from './DialogLogView'
import VerdictBadge from './VerdictBadge'



const SUMMARY_PREVIEW_LEN = 150



const cardBase = {

  background: '#FFFFFF',

  border: '1px solid #F0F0F0',

  borderRadius: 12,

  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',

  overflow: 'hidden',

}



function Section({ title, items }) {

  if (!items?.length) return null

  return (

    <div style={{ padding: '12px 16px', borderTop: '1px solid #F0F0F0' }}>

      <div

        style={{

          fontSize: 13,

          fontWeight: 600,

          color: '#111827',

          marginBottom: 8,

          display: 'flex',

          alignItems: 'center',

          gap: 6,

        }}

      >

        {title}

      </div>

      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.5 }}>

        {items.map((item, i) => (

          <li key={i} style={{ marginBottom: 4 }}>

            {item}

          </li>

        ))}

      </ul>

    </div>

  )

}



function toggleBtnStyle() {

  return {

    marginTop: 8,

    padding: 0,

    border: 'none',

    background: 'transparent',

    color: '#4F46E5',

    fontSize: 12,

    fontWeight: 500,

    cursor: 'pointer',

  }

}



export default function CandidateCard({

  screening,

  vacancyTitle,

  onStatusChange,

}) {

  const { showToast } = useToast()

  const [summaryExpanded, setSummaryExpanded] = useState(false)

  const [rejecting, setRejecting] = useState(false)

  const [forwarding, setForwarding] = useState(false)

  const [historyOpen, setHistoryOpen] = useState(false)

  const [history, setHistory] = useState([])

  const [historyLoading, setHistoryLoading] = useState(false)



  const name = candidateFullName(screening)

  const rejected = screening.status === 'rejected'

  const aiAnalysisPending = isAiAnalysisPending(screening)
  const aiAnalysisMissing = isAiAnalysisMissing(screening)
  const [reanalyzing, setReanalyzing] = useState(false)

  const isRepeated = (screening.screening_index ?? 1) > 1



  const { strengths, weaknesses, redFlags, aiMarkers } = screeningExtras(screening)

  const suspected = aiMarkers.suspected === true



  const summary = screening.summary?.trim() || ''

  const summaryLong = summary.length > SUMMARY_PREVIEW_LEN

  const summaryDisplay = summaryExpanded || !summaryLong

    ? summary

    : `${summary.slice(0, SUMMARY_PREVIEW_LEN)}...`



  const toggleHistory = async () => {
    const next = !historyOpen
    setHistoryOpen(next)
    if (!next || !screening.candidate_id) return
    setHistoryLoading(true)
    try {
      const { data } = await client.get(
        `/screenings/candidate/${screening.candidate_id}/history`
      )
      setHistory(data || [])
    } catch {
      setHistory([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleReanalyze = async () => {
    setReanalyzing(true)
    try {
      await client.post(`/screenings/${screening.id}/reanalyze`)
      showToast('Анализ резюме запущен повторно')
      onStatusChange?.(screening.id, screening.status)
    } catch {
      showToast('Не удалось запустить анализ', 'error')
    } finally {
      setReanalyzing(false)
    }
  }

  const handleForward = async () => {
    setForwarding(true)
    try {
      await client.patch(`/screenings/${screening.id}/status`, { status: 'forwarded' })
      showToast('Кандидат передан дальше')
      onStatusChange?.(screening.id, 'forwarded')
    } catch {
      showToast('Не удалось обновить статус', 'error')
    } finally {
      setForwarding(false)
    }
  }

  const handleReject = async () => {

    const confirmed = window.confirm(

      'Отправить кандидату уведомление об отказе в Telegram?'

    )

    if (!confirmed) return



    setRejecting(true)

    try {

      await client.post(`/screenings/${screening.id}/reject`)

      showToast('Кандидат отклонён, уведомление отправлено')

      onStatusChange?.(screening.id, 'rejected')

    } catch (e) {

      const detail = e.response?.data?.detail

      showToast(

        typeof detail === 'string' ? detail : 'Не удалось отклонить кандидата',

        'error'

      )

    } finally {

      setRejecting(false)

    }

  }



  const handleMessage = () => {

    const tid = screening.candidate_telegram_id

    if (!tid) {

      showToast('Telegram ID не указан', 'error')

      return

    }

    const url = `tg://user?id=${tid}`

    const opened = window.open(url, '_blank')

    if (!opened) {

      showToast('Откройте Telegram вручную по ID кандидата', 'error')

    }

  }



  return (

    <article

      style={{

        ...cardBase,

        opacity: rejected ? 0.65 : 1,

        background: rejected ? '#F9FAFB' : '#FFFFFF',

      }}

    >

      <div style={{ padding: 16 }}>

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>

          <Avatar
            name={screening.candidate_name || screening.candidate?.full_name}
            src={mediaUrl(
              screening.avatar_url ||
                screening.candidate?.avatar_file_path ||
                screening.avatar_file_path
            )}
            size={48}
          />

          <div style={{ flex: 1, minWidth: 0 }}>

            <div

              style={{

                display: 'flex',

                alignItems: 'flex-start',

                justifyContent: 'space-between',

                gap: 8,

                flexWrap: 'wrap',

              }}

            >

              <div style={{ flex: 1, minWidth: 0 }}>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>

                  <h3

                    style={{

                      fontSize: 16,

                      fontWeight: 600,

                      color: '#111827',

                      margin: 0,

                      ...nameTruncateStyle,

                    }}

                    title={name}

                  >

                    {name}

                  </h3>

                  {isRepeated && (

                    <span

                      style={{

                        fontSize: 11,

                        padding: '2px 8px',

                        borderRadius: 999,

                        background: '#EEF2FF',

                        color: '#4F46E5',

                        fontWeight: 500,

                      }}

                    >

                      {`Попытка ${screening.screening_index}`}

                    </span>

                  )}

                </div>

                {vacancyTitle && (

                  <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4, marginBottom: 0 }}>

                    {vacancyTitle}

                  </p>

                )}

              </div>

              <div style={{ textAlign: 'right', flexShrink: 0 }}>

                <VerdictBadge
                  verdict={screeningHrStatus(screening)}
                  label={screening.verdict_label}
                />

                {screening.score != null && (

                  <div style={{ fontSize: 12, color: '#6B7280', marginTop: 6 }}>

                    score: {screening.score}

                  </div>

                )}

              </div>

            </div>

          </div>

        </div>

      </div>



      {aiAnalysisPending && (
        <div style={{ padding: '0 16px 12px', fontSize: 13, color: '#6B7280' }}>
          ИИ анализирует резюме…
        </div>
      )}

      {aiAnalysisMissing && (
        <div
          style={{
            padding: '0 16px 12px',
            fontSize: 13,
            color: '#B45309',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            flexWrap: 'wrap',
          }}
        >
          <span>Оценка ИИ не получена (анализ не завершился или ИИ недоступен)</span>
          <button
            type="button"
            onClick={handleReanalyze}
            disabled={reanalyzing}
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              border: '1px solid #FDE68A',
              background: '#FFFBEB',
              color: '#B45309',
              fontSize: 12,
              cursor: reanalyzing ? 'wait' : 'pointer',
            }}
          >
            {reanalyzing ? 'Запуск…' : 'Повторить анализ'}
          </button>
        </div>
      )}



      {summary && (

        <div style={{ padding: '0 16px 16px' }}>

          <p

            style={{

              fontSize: 13,

              color: '#374151',

              lineHeight: 1.5,

              margin: 0,

              whiteSpace: 'pre-wrap',

            }}

          >

            {summaryDisplay}

          </p>

          {summaryLong && (

            <button

              type="button"

              onClick={() => setSummaryExpanded(!summaryExpanded)}

              style={toggleBtnStyle()}

            >

              {summaryExpanded ? 'Свернуть' : 'Подробнее'}

            </button>

          )}

        </div>

      )}



      <div style={{ padding: '0 16px 16px' }}>

        <ScoreBar
          score={screening.score}
          pending={aiAnalysisPending}
          missing={aiAnalysisMissing}
        />

        {screening.score_breakdown?.dimensions?.length > 0 && (
          <details style={{ marginTop: 12, fontSize: 13, color: '#374151' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
              Оценка по компетенциям
              {screening.score_breakdown.bucket && (
                <span style={{ marginLeft: 8, color: '#6B7280', fontWeight: 400 }}>
                  ({screening.score_breakdown.bucket})
                </span>
              )}
            </summary>
            <ul style={{ margin: '8px 0 0', paddingLeft: 18, lineHeight: 1.5 }}>
              {screening.score_breakdown.dimensions.map((d) => (
                <li key={d.id}>
                  {d.title || d.id}: {d.score_1_5}/5
                </li>
              ))}
            </ul>
          </details>
        )}

      </div>



      <Section

        title={

          <>

            <CheckCircle size={16} color="#22C55E" />

            Сильные стороны:

          </>

        }

        items={strengths}

      />

      <Section

        title={

          <>

            <AlertTriangle size={16} color="#F59E0B" />

            Слабые стороны:

          </>

        }

        items={weaknesses}

      />



      <div style={{ padding: '12px 16px', borderTop: '1px solid #F0F0F0' }}>

        {screening.resume_file_path ? (

          <div

            style={{

              marginTop: 12,

              padding: '10px 14px',

              background: '#F8F9FB',

              borderRadius: 8,

              border: '1px solid #F0F0F0',

              display: 'flex',

              alignItems: 'center',

              justifyContent: 'space-between',

            }}

          >

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>

              <FileText size={16} color="#4F46E5" />

              <span style={{ fontSize: 13, color: '#374151', fontWeight: 500 }}>

                Резюме PDF

              </span>

            </div>

            <div style={{ display: 'flex', gap: 8 }}>

              <a

                href={mediaUrl(screening.resume_url || screening.resume_file_path)}

                target="_blank"

                rel="noopener noreferrer"

                style={{

                  padding: '5px 12px',

                  background: '#EEF2FF',

                  color: '#4F46E5',

                  borderRadius: 6,

                  fontSize: 12,

                  fontWeight: 500,

                  textDecoration: 'none',

                  display: 'flex',

                  alignItems: 'center',

                  gap: 4,

                }}

              >

                <ExternalLink size={12} /> Открыть

              </a>

              <a

                href={mediaUrl(screening.resume_url || screening.resume_file_path)}

                download

                style={{

                  padding: '5px 12px',

                  background: '#F0FDF4',

                  color: '#166534',

                  borderRadius: 6,

                  fontSize: 12,

                  fontWeight: 500,

                  textDecoration: 'none',

                  display: 'flex',

                  alignItems: 'center',

                  gap: 4,

                }}

              >

                <Download size={12} /> Скачать

              </a>

            </div>

          </div>

        ) : (

          <div style={{ marginTop: 12, fontSize: 12, color: '#9CA3AF' }}>

            Резюме не прикреплено

          </div>

        )}

      </div>



      <div style={{ padding: '12px 16px', borderTop: '1px solid #F0F0F0' }}>

        <div

          style={{

            fontSize: 13,

            fontWeight: 600,

            color: '#111827',

            marginBottom: 6,

            display: 'flex',

            alignItems: 'center',

            gap: 6,

            flexWrap: 'wrap',

          }}

        >

          <Bot size={16} />

          ИИ-резюме:{' '}

          {suspected ? (

            <span style={{ color: '#DC2626' }}>

              подозрение ({aiMarkers.confidence || 'medium'})

            </span>

          ) : (

            <span style={{ color: '#16A34A', display: 'inline-flex', alignItems: 'center', gap: 4 }}>

              не обнаружено <CheckCircle size={16} color="#22C55E" />

            </span>

          )}

        </div>

        {suspected && aiMarkers.reasons?.length > 0 && (

          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: '#6B7280' }}>

            {aiMarkers.reasons.map((r, i) => (

              <li key={i}>{r}</li>

            ))}

          </ul>

        )}

        {redFlags.length > 0 && (

          <div style={{ marginTop: 8, fontSize: 12, color: '#B45309' }}>

            Флаги: {redFlags.join('; ')}

          </div>

        )}

      </div>



      <DialogLogView dialogLog={screening.dialog_log} />



      {screening.candidate_id && (

        <div style={{ padding: '12px 16px', borderTop: '1px solid #F0F0F0' }}>

          <button

            type="button"

            onClick={toggleHistory}

            style={{

              width: '100%',

              display: 'flex',

              alignItems: 'center',

              justifyContent: 'space-between',

              padding: 0,

              border: 'none',

              background: 'transparent',

              fontSize: 13,

              fontWeight: 600,

              color: '#111827',

              cursor: 'pointer',

            }}

          >

            История откликов

            {historyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}

          </button>

          {historyOpen && (

            <div style={{ marginTop: 10 }}>

              {historyLoading && (

                <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>Загрузка…</p>

              )}

              {!historyLoading && history.length === 0 && (

                <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>Нет других откликов</p>

              )}

              {!historyLoading &&

                history.map((item) => (

                  <div

                    key={item.id}

                    style={{

                      padding: '8px 0',

                      borderBottom: '1px solid #F3F4F6',

                      fontSize: 12,

                      color: '#374151',

                    }}

                  >

                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>

                      <span>
                        {item.vacancy_title || 'Вакансия'}
                        {' · '}
                        {new Date(item.created_at).toLocaleDateString('ru-RU')}
                        {item.screening_index > 1 ? ` · Попытка ${item.screening_index}` : ''}
                      </span>

                      <VerdictBadge verdict={screeningVerdict(item)} />

                    </div>

                    {item.score != null && (

                      <span style={{ color: '#6B7280' }}>Оценка: {item.score}</span>

                    )}

                  </div>

                ))}

            </div>

          )}

        </div>

      )}



      <div

        style={{

          padding: 16,

          borderTop: '1px solid #F0F0F0',

          display: 'flex',

          gap: 8,

          flexWrap: 'wrap',

        }}

      >

        <button

          type="button"

          onClick={handleMessage}

          disabled={rejected}

          style={{

            flex: 1,

            minWidth: 140,

            display: 'flex',

            alignItems: 'center',

            justifyContent: 'center',

            gap: 6,

            padding: '10px 14px',

            borderRadius: 8,

            border: '1px solid #E5E7EB',

            background: '#FFFFFF',

            fontSize: 13,

            fontWeight: 500,

            color: '#374151',

            opacity: rejected ? 0.5 : 1,

          }}

        >

          <Mail size={16} /> Открыть в Telegram

        </button>

        <button
          type="button"
          onClick={handleForward}
          disabled={forwarding || rejected || screening.status === 'forwarded'}
          style={{
            flex: 1,
            minWidth: 120,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid #C7D2FE',
            background: '#EEF2FF',
            fontSize: 13,
            fontWeight: 500,
            color: '#4F46E5',
            opacity: rejected || screening.status === 'forwarded' ? 0.5 : 1,
          }}
        >
          Передан дальше
        </button>

        <button

          type="button"

          onClick={handleReject}

          disabled={rejecting || rejected}

          style={{

            flex: 1,

            minWidth: 120,

            display: 'flex',

            alignItems: 'center',

            justifyContent: 'center',

            gap: 6,

            padding: '10px 14px',

            borderRadius: 8,

            border: '1px solid #FECACA',

            background: '#FFF1F2',

            fontSize: 13,

            fontWeight: 500,

            color: '#9F1239',

            opacity: rejected ? 0.5 : 1,

          }}

        >

          <X size={16} /> Отклонить

        </button>

      </div>

    </article>

  )

}

