import { useCallback, useEffect, useRef, useState } from 'react'
import { useThreadStore } from '../../store/useThreadStore'
import { useChannelStore } from '../../store/useChannelStore'
import Message from './Message'
import ThinkingRow from './ThinkingRow'
import AvatarStack from '../ui/AvatarStack'
import Icon, { Ico } from '../ui/Icon'

function EmptyState({ roster }) {
  const starters = ['¿Qué opináis sobre esto?', '¿Por dónde empezamos?', 'Quiero debatir una idea']
  return (
    <div className="t-empty">
      <AvatarStack profiles={roster} size={40} />
      <div className="t-empty-title">Canal listo</div>
      <div className="t-empty-sub">Escribe para empezar el debate</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 12 }}>
        {starters.map((s) => (
          <span key={s} className="t-badge" style={{ cursor: 'default' }}>{s}</span>
        ))}
      </div>
    </div>
  )
}

export default function Thread() {
  const { messages, thinking } = useThreadStore()
  const { roster, activeChannelId } = useChannelStore()
  const bottomRef = useRef(null)
  const threadRef = useRef(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const isStreaming = thinking.size > 0 || messages.some((m) => m.streaming)

  const handleScroll = useCallback(() => {
    const el = threadRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    setAutoScroll(atBottom)
  }, [])

  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, thinking, autoScroll])

  const resumeScroll = () => setAutoScroll(true)

  if (!activeChannelId) {
    return (
      <div className="t-thread t-scroll">
        <div className="t-thread-inner">
          <div className="t-empty" style={{ marginTop: 80, textAlign: 'center' }}>
            <div className="t-empty-title">Selecciona un canal</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="t-thread t-scroll" ref={threadRef} onScroll={handleScroll}>
      <div className="t-thread-inner">
        {messages.length === 0 ? (
          <EmptyState roster={roster} />
        ) : (
          <>
            <div className="t-daysep"><span>hoy</span></div>
            {messages.map((m) => <Message key={m.id} message={m} />)}
            {[...thinking].map((profileId) => (
              <ThinkingRow key={profileId} profileId={profileId} />
            ))}
          </>
        )}
        {!autoScroll && (
          <div className="t-autoscroll-anchor">
            <button className="t-autoscroll-btn" onClick={resumeScroll}>
              <Icon d={Ico.chevron} size={13} />
              {isStreaming ? 'Reanudar scroll' : 'Ir al final'}
            </button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
