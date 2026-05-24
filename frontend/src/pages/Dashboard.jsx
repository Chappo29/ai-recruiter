import { useEffect, useState } from 'react'

import { useNavigate } from 'react-router-dom'

import { AlertTriangle, Bot, Briefcase, Star, Users } from 'lucide-react'

import client, { API_BASE_URL } from '../api/client'

import Avatar from '../components/Avatar'

import MetricCard from '../components/MetricCard'

import { PageTopbar } from '../components/Sidebar'

import ScoreBar from '../components/ScoreBar'

import VerdictBadge from '../components/VerdictBadge'

import { candidateFullName, nameTruncateStyle, screeningVerdict } from '../utils/candidate'

import { screeningExtras } from '../utils/parseJSON'

import { MetricSkeleton } from '../components/Skeleton'



const EMPTY_METRICS = {

  activeVacancies: 0,

  totalCandidates: 0,

  fitCount: 0,

  suspectedCount: 0,

}



function todayLabel() {

  return new Date().toLocaleDateString('ru-RU', {

    weekday: 'long',

    day: 'numeric',

    month: 'long',

  })

}



export default function Dashboard() {

  const navigate = useNavigate()

  const [vacancies, setVacancies] = useState([])

  const [recentScreenings, setRecentScreenings] = useState([])

  const [metrics, setMetrics] = useState(EMPTY_METRICS)

  const [loading, setLoading] = useState(true)



  useEffect(() => {

    const load = async () => {

      try {

        const { data: vacs } = await client.get('/vacancies/')

        setVacancies(vacs || [])

        const active = (vacs || []).filter((v) => v.status === 'active').length



        const [statsRes, recentRes] = await Promise.all([
          client.get('/screenings/stats').catch(() => ({ data: [] })),
          client.get('/screenings/recent', { params: { limit: 5 } }).catch(() => ({ data: [] })),
        ])

        const statsRows = statsRes.data || []
        const recent = recentRes.data || []
        setRecentScreenings(recent)

        const totalFromStats = statsRows.reduce((sum, row) => sum + (row.total || 0), 0)
        const fitFromStats = statsRows.reduce((sum, row) => sum + (row.fit || 0), 0)

        setMetrics({
          activeVacancies: active,
          totalCandidates: totalFromStats,
          fitCount: fitFromStats,
          suspectedCount: recent.filter((s) => {
            const { aiMarkers: am } = screeningExtras(s)
            return am.suspected === true
          }).length,
        })

      } catch {

        setVacancies([])

        setRecentScreenings([])

        setMetrics(EMPTY_METRICS)

      } finally {

        setLoading(false)

      }

    }

    load()

  }, [])



  return (

    <div>

      <PageTopbar title="Дашборд" subtitle={todayLabel()}>

        <div style={{ display: 'flex', gap: 8 }}>

          <button

            type="button"

            onClick={() => navigate('/vacancies')}

            style={{

              padding: '8px 14px',

              borderRadius: 8,

              border: 'none',

              background: '#4F46E5',

              color: '#FFFFFF',

              fontSize: 13,

              fontWeight: 500,

            }}

          >

            + Вакансия

          </button>

        </div>

      </PageTopbar>



      <div style={{ padding: 24 }}>

        <div

          style={{

            display: 'grid',

            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',

            gap: 12,

            marginBottom: 24,

          }}

        >

          {loading ? (

            <>

              <MetricSkeleton />

              <MetricSkeleton />

              <MetricSkeleton />

              <MetricSkeleton />

            </>

          ) : (

            <>

              <MetricCard

                icon={Briefcase}

                iconBg="#EEF2FF"

                iconColor="#4F46E5"

                value={metrics.activeVacancies}

                label="Активных вакансий"

              />

              <MetricCard

                icon={Users}

                iconBg="#F0FDF4"

                iconColor="#22C55E"

                value={metrics.totalCandidates}

                label="Кандидатов всего"

              />

              <MetricCard

                icon={Star}

                iconBg="#FFFBEB"

                iconColor="#F59E0B"

                value={metrics.fitCount}

                label="Подходящих"

              />

              <MetricCard

                icon={AlertTriangle}

                iconBg="#FFF1F2"

                iconColor="#F43F5E"

                value={metrics.suspectedCount}

                label="Вкатунов"

              />

            </>

          )}

        </div>



        <div

          style={{

            display: 'grid',

            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',

            gap: 16,

          }}

        >

          <section

            style={{

              background: '#FFFFFF',

              border: '1px solid #F0F0F0',

              borderRadius: 12,

              padding: 16,

              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',

            }}

          >

            <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Вакансии</h2>

            {vacancies.length === 0 && (

              <p style={{ fontSize: 13, color: '#9CA3AF' }}>Нет вакансий</p>

            )}

            {vacancies.slice(0, 6).map((v) => (

              <button

                key={v.id}

                type="button"

                onClick={() => navigate(`/candidates?vacancy_id=${v.id}`)}

                style={{

                  width: '100%',

                  display: 'flex',

                  alignItems: 'center',

                  gap: 12,

                  padding: '10px 0',

                  borderBottom: '1px solid #F9FAFB',

                  border: 'none',

                  background: 'transparent',

                  textAlign: 'left',

                  cursor: 'pointer',

                }}

              >

                <div

                  style={{

                    width: 36,

                    height: 36,

                    borderRadius: 8,

                    background: '#EEF2FF',

                    color: '#4F46E5',

                    display: 'flex',

                    alignItems: 'center',

                    justifyContent: 'center',

                  }}

                >

                  <Briefcase size={16} />

                </div>

                <div style={{ flex: 1, minWidth: 0 }}>

                  <div style={{ fontSize: 14, fontWeight: 500, color: '#111827' }}>{v.title}</div>

                  <div style={{ fontSize: 12, color: '#9CA3AF' }}>

                    {v.status === 'active' ? 'Активна' : 'Закрыта'}

                  </div>

                </div>

              </button>

            ))}

          </section>



          <section

            style={{

              background: '#FFFFFF',

              border: '1px solid #F0F0F0',

              borderRadius: 12,

              padding: 16,

              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',

            }}

          >

            <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>

              Последние кандидаты

            </h2>

            {recentScreenings.length === 0 && (

              <p style={{ fontSize: 13, color: '#9CA3AF' }}>

                Кандидаты появятся после откликов через бота

              </p>

            )}

            {recentScreenings.map((s) => {

              const name = candidateFullName(s)

              const { aiMarkers } = screeningExtras(s)

              const suspected = aiMarkers.suspected === true



              return (

                <div

                  key={s.id}

                  style={{

                    display: 'flex',

                    alignItems: 'center',

                    gap: 12,

                    padding: '10px 0',

                    borderBottom: '1px solid #F9FAFB',

                  }}

                >

                  <Avatar
                    name={name}
                    src={
                      (s.candidate?.avatar_file_path || s.avatar_file_path)
                        ? `${API_BASE_URL}${s.candidate?.avatar_file_path || s.avatar_file_path}`
                        : null
                    }
                    size={36}
                  />

                  <div style={{ flex: 1, minWidth: 0 }}>

                    <div

                      style={{

                        display: 'flex',

                        alignItems: 'center',

                        gap: 6,

                        marginBottom: 6,

                        flexWrap: 'wrap',

                      }}

                    >

                      <span

                        style={{

                          fontSize: 13,

                          fontWeight: 500,

                          ...nameTruncateStyle,

                        }}

                        title={name}

                      >

                        {name}

                      </span>

                      {suspected && (

                        <Bot size={14} color="#DC2626" title="Подозрение на ИИ" />

                      )}

                    </div>

                    <ScoreBar score={s.score} pending={s.status === 'pending'} />

                  </div>

                  <VerdictBadge verdict={screeningVerdict(s)} />

                </div>

              )

            })}

          </section>

        </div>

      </div>

    </div>

  )

}

