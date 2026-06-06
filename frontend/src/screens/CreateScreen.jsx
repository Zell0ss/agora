import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../components/ui/Icon'
import Avatar from '../components/ui/Avatar'
import { getProfiles, createChannel, addToRoster } from '../services/api'
import { useChannelStore } from '../store/useChannelStore'

function ModeCard({ active, title, desc, onClick }) {
  return (
    <div className={`t-modecard${active ? ' is-on' : ''}`} onClick={onClick} style={{ cursor: 'pointer' }}>
      <div className="t-modecard-t"><span className="t-modedot" />{title}</div>
      <div className="t-modecard-d">{desc}</div>
    </div>
  )
}

export default function CreateScreen() {
  const navigate = useNavigate()
  const { addChannel, setActive } = useChannelStore()

  const [title, setTitle] = useState('')
  const [mode, setMode] = useState('debate')
  const [profiles, setProfiles] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getProfiles().then((ps) => setProfiles(ps.filter((p) => !p.archived)))
  }, [])

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 3) next.add(id)
      return next
    })
  }

  const full = selected.size >= 3

  const handleCreate = async () => {
    if (selected.size === 0 || saving) return
    setSaving(true)
    try {
      const channel = await createChannel({ title: title || 'Sin título', mode })
      let order = 0
      for (const profileId of selected) {
        await addToRoster(channel.id, { profile_id: profileId, speaking_order: order++ })
      }
      addChannel(channel)
      await setActive(channel.id)
      navigate('/')
    } catch (err) {
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="t-sheet">
      <div className="t-sheet-head">
        <div>
          <div className="t-sheet-eyebrow">Nuevo canal</div>
          <div className="t-sheet-title">¿De qué hablamos?</div>
        </div>
        <div className="t-head-spacer" />
        <button className="t-iconbtn" onClick={() => navigate('/')}>✕</button>
      </div>

      <div className="t-sheet-body t-scroll">
        <div className="t-sheet-inner">
          <div>
            <div className="t-field-label">Título del canal</div>
            <input
              className="t-titlefield"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Newsletter de urbanismo…"
              style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }}
            />
          </div>

          <div>
            <div className="t-field-label">Modo</div>
            <div className="t-modeseg">
              <ModeCard
                active={mode === 'debate'} title="Debate"
                desc="Para discutir una idea: los tertulianos la tensan entre todos."
                onClick={() => setMode('debate')}
              />
              <ModeCard
                active={mode === 'critica'} title="Crítica"
                desc="Para revisar un texto: lo leen y te lo devuelven con notas."
                onClick={() => setMode('critica')}
              />
            </div>
          </div>

          <div>
            <div className="t-pickhead">
              <div className="t-field-label" style={{ margin: 0 }}>Tertulianos · elige 1–3</div>
              <span className={`t-pickcount${full ? ' is-full' : ''}`}>
                {selected.size} / 3{full ? ' · completo' : ''}
              </span>
            </div>
            <div className="t-picklist">
              {profiles.map((p) => {
                const isSel = selected.has(p.id)
                const dim = full && !isSel
                return (
                  <div
                    key={p.id}
                    className={`t-prow${isSel ? ' is-sel' : ''}${dim ? ' is-dim' : ''}`}
                    onClick={() => toggle(p.id)}
                    style={{ cursor: dim ? 'default' : 'pointer' }}
                  >
                    <Avatar profile={p} size={38} />
                    <div className="t-prow-body">
                      <div className="t-prow-top">
                        <span className="t-prow-name" data-voice={p.color}>{p.name}</span>
                        {p.funcion && <span className="t-rolechip">· {p.funcion.toLowerCase()}</span>}
                        {p.tipo === 'facilitador' && <span className="t-tag-fac">facilitador</span>}
                      </div>
                    </div>
                    <div className={`t-check${isSel ? ' is-on' : ''}`}>
                      <Icon d={Ico.check} size={13} stroke={2} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="t-sheet-foot">
        <button className="t-btn is-ghost" onClick={() => navigate('/')}>Cancelar</button>
        <button
          className="t-btn is-primary"
          onClick={handleCreate}
          disabled={selected.size === 0 || saving}
        >
          {saving ? 'Creando…' : 'Abrir canal'}
        </button>
      </div>
    </div>
  )
}
