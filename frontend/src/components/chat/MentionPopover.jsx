import { useEffect } from 'react'
import Avatar from '../ui/Avatar'

export default function MentionPopover({ profiles, filter, onSelect, onClose }) {
  const normalize = (s) =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

  const filtered = profiles.filter((p) =>
    normalize(p.name).startsWith(normalize(filter))
  )

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (filtered.length === 0) return null

  return (
    <div className="t-mentionpop">
      {filtered.map((p) => (
        <div
          key={p.profile_id}
          className="t-prow"
          style={{ cursor: 'pointer', padding: '8px 12px' }}
          onMouseDown={(e) => { e.preventDefault(); onSelect(p.name) }}
        >
          <Avatar profile={p} size={28} />
          <div className="t-prow-body">
            <div className="t-prow-top">
              <span className="t-prow-name" data-voice={p.color}>{p.name}</span>
              {p.funcion && <span className="t-rolechip">· {p.funcion.toLowerCase()}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
