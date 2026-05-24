import { useCallback, useEffect, useState } from 'react'
import { Bot, ClipboardList, Copy, HelpCircle, Link, Loader2, Play, Square } from 'lucide-react'
import client from '../api/client'
import { useToast } from '../components/Toast'

export default function BotSettings() {
  const { showToast } = useToast()
  const [token, setToken] = useState('')
  const [status, setStatus] = useState(null)
  const [tokenInfo, setTokenInfo] = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [action, setAction] = useState(null)
  const [editingToken, setEditingToken] = useState(false)

  const loadStatus = useCallback(async () => {
    setStatusLoading(true)
    try {
      const [statusRes, tokenRes] = await Promise.all([
        client.get('/bots/status'),
        client.get('/bots/token'),
      ])
      setStatus(statusRes.data)
      setTokenInfo(tokenRes.data)
    } catch {
      setStatus(null)
      setTokenInfo(null)
    } finally {
      setStatusLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  const isRunning = status?.status === 'running'
  const busy = action !== null
  const hasToken = Boolean(tokenInfo?.has_token)
  const showTokenInput = !hasToken || editingToken
  const botLink =
    isRunning && status?.bot_username
      ? `t.me/${status.bot_username}`
      : null

  const startBot = async () => {
    if (!token.trim() && !hasToken) {
      showToast('Введите токен бота', 'error')
      return
    }
    setAction('start')
    try {
      const body = token.trim() ? { token: token.trim() } : {}
      await client.post('/bots/start', body)
      showToast(hasToken && editingToken ? 'Токен обновлён' : 'Бот запущен')
      setToken('')
      setEditingToken(false)
      await loadStatus()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Ошибка запуска', 'error')
    } finally {
      setAction(null)
    }
  }

  const stopBot = async () => {
    setAction('stop')
    try {
      await client.post('/bots/stop')
      showToast('Бот остановлен')
      await loadStatus()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Ошибка остановки', 'error')
    } finally {
      setAction(null)
    }
  }

  const copyLink = async () => {
    if (!botLink) return
    try {
      await navigator.clipboard.writeText(`https://${botLink}`)
      showToast('Ссылка скопирована')
    } catch {
      showToast('Не удалось скопировать', 'error')
    }
  }

  return (
    <div style={{ padding: 24, display: 'flex', justifyContent: 'center' }}>
      <div
        style={{
          width: '100%',
          maxWidth: 520,
          background: '#FFFFFF',
          border: '1px solid #F0F0F0',
          borderRadius: 12,
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #F0F0F0' }}>
          <h1
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: '#111827',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Bot size={22} color="#4F46E5" />
            Настройка Telegram-бота
          </h1>
        </div>

        <div style={{ padding: 24 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 20,
              fontSize: 14,
            }}
          >
            {statusLoading ? (
              <>
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                <span style={{ color: '#6B7280' }}>Загрузка статуса…</span>
              </>
            ) : (
              <>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: isRunning ? '#22C55E' : '#D1D5DB',
                    flexShrink: 0,
                  }}
                />
                <span style={{ color: '#374151' }}>
                  Статус:{' '}
                  <strong style={{ color: isRunning ? '#166534' : '#6B7280' }}>
                    {isRunning ? 'Активен' : 'Не запущен'}
                  </strong>
                </span>
              </>
            )}
          </div>

          {hasToken && !showTokenInput && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                Сохранённый токен
              </label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid #E5E7EB',
                  background: '#F9FAFB',
                  fontSize: 14,
                  fontFamily: 'monospace',
                  color: '#374151',
                  marginBottom: 8,
                }}
              >
                {tokenInfo.masked}
              </div>
              <button
                type="button"
                onClick={() => {
                  setEditingToken(true)
                  setToken('')
                }}
                disabled={busy || statusLoading}
                style={{
                  padding: 0,
                  border: 'none',
                  background: 'transparent',
                  color: '#4F46E5',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: busy || statusLoading ? 'not-allowed' : 'pointer',
                }}
              >
                Изменить токен
              </button>
            </div>
          )}

          {showTokenInput && (
            <>
              <label
                style={{
                  fontSize: 13,
                  color: '#6B7280',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  marginBottom: 6,
                }}
              >
                Bot Token
                <span title="Получите у @BotFather" style={{ cursor: 'help' }}>
                  <HelpCircle size={14} />
                </span>
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="123456789:ABCdefGHI..."
                disabled={busy}
                style={{
                  width: '100%',
                  border: '1px solid #E5E7EB',
                  borderRadius: 8,
                  padding: '10px 14px',
                  fontSize: 14,
                  marginBottom: 12,
                }}
              />
              {!hasToken ? (
                <button
                  type="button"
                  onClick={startBot}
                  disabled={busy || statusLoading}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    padding: 11,
                    marginBottom: 16,
                    background: busy || statusLoading ? '#E5E7EB' : '#4F46E5',
                    color: busy || statusLoading ? '#9CA3AF' : '#FFFFFF',
                    border: 'none',
                    borderRadius: 8,
                    fontWeight: 500,
                    fontSize: 13,
                    cursor: busy || statusLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {action === 'start' ? (
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  ) : (
                    <Play size={16} />
                  )}
                  {action === 'start' ? 'Сохранение…' : 'Сохранить и запустить'}
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                  <button
                    type="button"
                    onClick={startBot}
                    disabled={busy || statusLoading || !token.trim()}
                    style={{
                      flex: 1,
                      padding: 11,
                      background: busy || !token.trim() ? '#E5E7EB' : '#4F46E5',
                      color: busy || !token.trim() ? '#9CA3AF' : '#FFFFFF',
                      border: 'none',
                      borderRadius: 8,
                      fontWeight: 500,
                      fontSize: 13,
                      cursor: busy || !token.trim() ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {action === 'start' ? 'Сохранение…' : 'Сохранить'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingToken(false)
                      setToken('')
                    }}
                    disabled={busy}
                    style={{
                      flex: 1,
                      padding: 11,
                      background: '#FFFFFF',
                      border: '1px solid #E5E7EB',
                      borderRadius: 8,
                      fontSize: 13,
                      color: '#374151',
                    }}
                  >
                    Отмена
                  </button>
                </div>
              )}
            </>
          )}

          {hasToken && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
              <button
                type="button"
                onClick={startBot}
                disabled={busy || statusLoading || isRunning || showTokenInput}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  padding: 11,
                  background: isRunning || busy || showTokenInput ? '#E5E7EB' : '#4F46E5',
                  color: isRunning || busy || showTokenInput ? '#9CA3AF' : '#FFFFFF',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 500,
                  fontSize: 13,
                  cursor: isRunning || busy || showTokenInput ? 'not-allowed' : 'pointer',
                }}
              >
                {action === 'start' ? (
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <Play size={16} />
                )}
                {action === 'start' ? 'Запуск…' : 'Запустить бота'}
              </button>
              <button
                type="button"
                onClick={stopBot}
                disabled={busy || statusLoading || !isRunning}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  padding: 11,
                  background: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: 8,
                  fontSize: 13,
                  color: !isRunning || busy ? '#9CA3AF' : '#374151',
                  cursor: !isRunning || busy ? 'not-allowed' : 'pointer',
                }}
              >
                {action === 'stop' ? (
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <Square size={16} />
                )}
                {action === 'stop' ? 'Остановка…' : 'Остановить'}
              </button>
            </div>
          )}

          <div
            style={{
              padding: 16,
              borderRadius: 8,
              background: '#F9FAFB',
              border: '1px solid #F0F0F0',
              marginBottom: 20,
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                marginBottom: 10,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <ClipboardList size={16} />
              Инструкция
            </div>
            <ol
              style={{
                margin: 0,
                paddingLeft: 20,
                fontSize: 13,
                color: '#374151',
                lineHeight: 1.6,
              }}
            >
              <li>Откройте @BotFather в Telegram</li>
              <li>Напишите /newbot</li>
              <li>Придумайте имя и username</li>
              <li>Скопируйте токен в поле выше</li>
            </ol>
          </div>

          {botLink && (
            <>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 8,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Link size={16} />
                Ссылка для кандидатов
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid #E5E7EB',
                  background: '#F9FAFB',
                }}
              >
                <span style={{ flex: 1, fontSize: 14, color: '#4F46E5' }}>{botLink}</span>
                <button
                  type="button"
                  onClick={copyLink}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '6px 10px',
                    borderRadius: 6,
                    border: '1px solid #E5E7EB',
                    background: '#FFFFFF',
                    fontSize: 12,
                    color: '#374151',
                  }}
                >
                  <Copy size={14} /> Скопировать
                </button>
              </div>
            </>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
