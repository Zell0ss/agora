import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Avatar from '../ui/Avatar'
import { useChannelStore } from '../../store/useChannelStore'

const MENTION_RE = /(@\S+)/g

function MentionText({ children }) {
  if (typeof children !== 'string') return children
  const parts = children.split(MENTION_RE)
  return parts.map((s, i) =>
    s.match(MENTION_RE)
      ? <span key={i} className="t-mention">{s}</span>
      : s
  )
}

const MD_COMPONENTS = {
  p: ({ children }) => <p><MentionText>{children}</MentionText></p>,
  li: ({ children }) => <li><MentionText>{children}</MentionText></li>,
}

function MarkdownContent({ text, streaming }) {
  return (
    <div className="t-md-msg">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
        {text}
      </ReactMarkdown>
      {streaming && <span className="t-caret" />}
    </div>
  )
}


export default function Message({ message }) {
  const roster = useChannelStore((s) => s.roster)

  if (message.role === 'human') {
    return (
      <div className="t-msg is-user">
        <div className="t-bubble is-user">
          <MarkdownContent text={message.content} streaming={message.streaming} />
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
        <MarkdownContent text={message.content} streaming={message.streaming} />
      </div>
    </div>
  )
}
