import { useState } from 'react'
import Icon, { Ico } from '../ui/Icon'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'

function buildMarkdown(channel, messages, roster) {
  if (!channel) return ''
  const rosterById = Object.fromEntries(roster.map((p) => [p.profile_id, p]))
  const lines = []
  lines.push(`# ${channel.title || 'Sin título'}`)
  lines.push(`_${channel.mode === 'debate' ? 'Debate' : 'Crítica'} · ${roster.map((p) => p.name).join(', ')} · Agora_`)
  lines.push('')
  for (const m of messages) {
    if (m.role === 'human') {
      lines.push(`**Tú** · ${m.time ?? ''}`)
    } else {
      const p = rosterById[m.profileId]
      lines.push(`**${p?.name ?? '?'}** _(${p?.funcion?.toLowerCase() ?? ''})_ · ${m.time ?? ''}`)
    }
    lines.push('')
    lines.push(m.content)
    lines.push('')
    lines.push('---')
    lines.push('')
  }
  return lines.join('\n')
}

export default function ExportModal({ onClose }) {
  const { channels, activeChannelId, roster } = useChannelStore()
  const messages = useThreadStore((s) => s.messages)
  const channel = channels.find((c) => c.id === activeChannelId)
  const md = buildMarkdown(channel, messages, roster)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(md)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = md
      ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="t-modal-backdrop" onClick={onClose}>
      <div className="t-modal" onClick={(e) => e.stopPropagation()}>
        <div className="t-modal-head">
          <div>
            <div className="t-sheet-eyebrow">Exportar conversación</div>
            <div className="t-modal-title">Markdown</div>
          </div>
          <div className="t-head-spacer" />
          <button className="t-iconbtn" onClick={onClose}>✕</button>
        </div>
        <div className="t-modal-bar">
          <span className="t-modal-hint">Texto sin formato · pégalo donde quieras</span>
          <div className="t-head-spacer" />
          <button className="t-btn is-sm is-primary" onClick={copy}>
            <Icon d={Ico.copy} size={15} />{copied ? '✓ Copiado' : 'Copiar'}
          </button>
        </div>
        <div className="t-modal-body t-scroll">
          <pre className="t-md" style={{ userSelect: 'all' }}>{md}</pre>
        </div>
      </div>
    </div>
  )
}
