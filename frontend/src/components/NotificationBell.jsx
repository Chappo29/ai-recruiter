import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import client, { API_BASE_URL } from '../api/client'

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'только что'
  if (m < 60) return `${m} мин назад`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} ч назад`
  return `${Math.floor(h / 24)} дн назад`
}

export default function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const containerRef = useRef(null)

  const fetchCount = useCallback(async () => {
    try {
      const { data } = await client.get('/notifications/unread-count')
      setUnreadCount(data.count || 0)
    } catch {}
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await client.get('/notifications/')
      setNotifications(data || [])
    } catch {} finally {
      setLoading(false)
    }
  }, [])

  // SSE for real-time updates; 30s polling as fallback
  useEffect(() => {
    const es = new EventSource(`${API_BASE_URL}/notifications/stream`, {
      withCredentials: true,
    })

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (typeof payload.unread_count === 'number') {
          setUnreadCount(payload.unread_count)
        }
        if (payload.notification) {
          setUnreadCount((c) => c + 1)
          setNotifications((prev) => [payload.notification, ...prev].slice(0, 30))
        }
      } catch {}
    }

    const timer = setInterval(fetchCount, 30000)
    return () => {
      es.close()
      clearInterval(timer)
    }
  }, [fetchCount])

  // Close panel on outside click
  useEffect(() => {
    if (!open) return
    const handle = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const handleToggle = () => {
    if (!open) fetchList()
    setOpen((o) => !o)
  }

  const handleItemClick = async (n) => {
    if (!n.read_at) {
      try {
        await client.post(`/notifications/${n.id}/read`)
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x))
        )
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {}
    }
    setOpen(false)
    if (n.action_url) navigate(n.action_url)
  }

  const handleMarkAll = async () => {
    try {
      await client.post('/notifications/read-all')
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() }))
      )
      setUnreadCount(0)
    } catch {}
  }

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={handleToggle}
        title="Уведомления"
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          border: 'none',
          background: open ? '#EEF2FF' : 'transparent',
          color: open ? '#4F46E5' : '#6B7280',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          position: 'relative',
          flexShrink: 0,
        }}
      >
        <Bell size={17} />
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: 2,
              right: 2,
              minWidth: 15,
              height: 15,
              borderRadius: 8,
              background: '#EF4444',
              color: '#FFFFFF',
              fontSize: 9,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 3px',
              lineHeight: 1,
            }}
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: 40,
            left: 0,
            width: 340,
            maxHeight: 420,
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: 12,
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            zIndex: 200,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: '1px solid #F0F0F0',
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>
              Уведомления
            </span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAll}
                style={{
                  border: 'none',
                  background: 'transparent',
                  color: '#4F46E5',
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                Прочитать всё
              </button>
            )}
          </div>

          {/* List */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading && (
              <div
                style={{ padding: 16, textAlign: 'center', fontSize: 13, color: '#9CA3AF' }}
              >
                Загрузка…
              </div>
            )}
            {!loading && notifications.length === 0 && (
              <div
                style={{ padding: 20, textAlign: 'center', fontSize: 13, color: '#9CA3AF' }}
              >
                Нет уведомлений
              </div>
            )}
            {!loading &&
              notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '11px 16px 11px 13px',
                    border: 'none',
                    borderBottom: '1px solid #F9FAFB',
                    borderLeft: n.read_at ? 'none' : '3px solid #4F46E5',
                    background: n.read_at ? '#F9FAFB' : '#FFFFFF',
                    cursor: 'pointer',
                    display: 'block',
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: '#111827',
                      marginBottom: 2,
                    }}
                  >
                    {n.title}
                  </div>
                  <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>
                    {n.message}
                  </div>
                  <div style={{ fontSize: 11, color: '#9CA3AF' }}>{timeAgo(n.created_at)}</div>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
