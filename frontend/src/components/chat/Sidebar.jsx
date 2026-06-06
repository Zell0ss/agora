import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../ui/Icon'
import AvatarStack from '../ui/AvatarStack'
import { useAppStore } from '../../store/useAppStore'
import { useChannelStore } from '../../store/useChannelStore'

function ThemeToggle() {
  const { theme, toggleTheme } = useAppStore()
  return (
    <button className="t-themesw" onClick={toggleTheme} aria-label="Cambiar tema">
      <span className={`t-themesw-opt${theme === 'light' ? ' is-on' : ''}`}>
        <Icon d={Ico.sun} size={15} />
      </span>
      <span className={`t-themesw-opt${theme === 'dark' ? ' is-on' : ''}`}>
        <Icon d={Ico.moon} size={14} />
      </span>
    </button>
  )
}

export default function Sidebar({ onChannelSelect }) {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const { channels, activeChannelId, setActive } = useChannelStore()

  const filtered = channels.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <aside className="t-side">
      <div className="t-side-top">
        <div className="t-brandrow">
          <div className="t-wordmark">Agora<span className="dot">.</span></div>
          <ThemeToggle />
        </div>
        <button className="t-newbtn" onClick={() => navigate('/channels/new')}>
          <Icon d={Ico.plus} size={18} />Nuevo canal
        </button>
      </div>

      <div className="t-search">
        <Icon d={Ico.search} size={16} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar canal…"
          style={{ background: 'none', border: 'none', outline: 'none', flex: 1, font: 'inherit', color: 'inherit' }}
        />
      </div>

      <div className="t-side-list t-scroll">
        <div className="t-side-label">Canales</div>
        {filtered.map((c) => (
          <div
            key={c.id}
            className={`t-chan${c.id === activeChannelId ? ' is-active' : ''}`}
            onClick={() => { setActive(c.id); onChannelSelect?.() }}
            style={{ cursor: 'pointer' }}
          >
            <div className="t-chan-av">
              <AvatarStack
                profiles={c.roster ?? []}
                size={26}
                ring={c.id === activeChannelId ? 'var(--surface)' : 'var(--sidebar)'}
              />
            </div>
            <div className="t-chan-mid">
              <div className="t-chan-title">{c.title || 'Sin título'}</div>
              <div className="t-chan-prev">{c.preview ?? ''}</div>
            </div>
            <div className="t-chan-right">
              <span className="t-chan-time">{c.time ?? ''}</span>
              <span className="t-chan-mode">{c.mode?.toUpperCase()}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="t-ed-list-foot">
        <button className="t-btn is-sm is-ghost" style={{ width: '100%', justifyContent: 'flex-start', gap: 8 }} onClick={() => navigate('/profiles')}>
          <Icon d={Ico.users} size={15} />Tertulianos
        </button>
      </div>
    </aside>
  )
}
