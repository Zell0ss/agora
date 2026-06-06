import { useEffect, useRef } from 'react'
import { useThreadStore } from '../../store/useThreadStore'
import { useChannelStore } from '../../store/useChannelStore'
import Message from './Message'
import ThinkingRow from './ThinkingRow'
import AvatarStack from '../ui/AvatarStack'

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
  const isStreaming = thinking.size > 0 || messages.some((m) => m.streaming)

  useEffect(() => {
    if (isStreaming || messages.length === 0) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, thinking, isStreaming])

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
    <div className="t-thread t-scroll">
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
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
