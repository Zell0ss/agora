import Avatar from '../ui/Avatar'
import { useChannelStore } from '../../store/useChannelStore'

function renderText(text) {
  const parts = text.split(/(@\w+)/g)
  return parts.map((s, i) =>
    s.startsWith('@')
      ? <span key={i} className="t-mention">{s}</span>
      : <span key={i}>{s}</span>
  )
}

export default function Message({ message }) {
  const roster = useChannelStore((s) => s.roster)

  if (message.role === 'human') {
    return (
      <div className="t-msg is-user">
        <div className="t-bubble is-user">
          <div className="t-msg-text">{renderText(message.content)}</div>
          {message.time && <span className="t-time t-bubble-time">{message.time}</span>}
        </div>
      </div>
    )
  }

  const profile = roster.find((p) => p.profile_id === message.profileId)

  return (
    <div className="t-msg is-tert row-tint" data-voice={profile?.color ?? 'vera'}>
      <Avatar profile={profile} size={34} />
      <div className="t-msg-body">
        <div className="t-msg-head">
          <span className="t-msg-name">{profile?.name ?? '…'}</span>
          {profile?.funcion && (
            <span className="t-rolechip">· {profile.funcion.toLowerCase()}</span>
          )}
          {message.time && <span className="t-time">{message.time}</span>}
        </div>
        <div className="t-msg-text">
          {renderText(message.content)}
          {message.streaming && <span className="t-caret" />}
        </div>
      </div>
    </div>
  )
}
