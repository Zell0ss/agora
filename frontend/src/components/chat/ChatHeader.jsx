import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../ui/Icon'
import AvatarStack from '../ui/AvatarStack'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'

export default function ChatHeader({ onExport, onSynthesize, onBack }) {
  const navigate = useNavigate()
  const { channels, activeChannelId, roster } = useChannelStore()
  const accumulatedCost = useThreadStore((s) => s.accumulatedCost)

  const channel = channels.find((c) => c.id === activeChannelId)
  if (!channel) return <header className="t-head" />

  const costNum = parseFloat(accumulatedCost)
  const costLabel = costNum > 0
    ? `· ${costNum.toLocaleString('es', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} €`
    : ''

  return (
    <header className="t-head">
      <button className="t-back-btn" onClick={onBack} aria-label="Volver">
        <Icon d={Ico.chevron} size={20} style={{ transform: 'rotate(90deg)' }} />
      </button>
      <div className="t-head-title">{channel.title || 'Sin título'}</div>
      {costLabel && <span className="t-cost">{costLabel}</span>}

      <div className="t-head-row-meta">
        <span className="t-badge is-mode">{channel.mode === 'debate' ? 'Debate' : 'Crítica'}</span>
        <div className="t-head-roster">
          <AvatarStack
            profiles={roster}
            size={28}
            ring="color-mix(in oklab, var(--paper) 85%, var(--surface))"
          />
          <button className="t-iconbtn" title="Gestionar tertulianos" onClick={() => navigate('/profiles')}>
            <Icon d={Ico.userplus} size={18} />
          </button>
        </div>
      </div>

      <div className="t-head-spacer" />

      <div className="t-head-row-actions">
        <button className="t-btn is-sm" onClick={onSynthesize}>
          <Icon d={Ico.sparkle} size={15} />Síntesis
        </button>
        <button className="t-btn is-sm" onClick={onExport}>
          <Icon d={Ico.export} size={16} />Exportar
        </button>
      </div>
    </header>
  )
}
