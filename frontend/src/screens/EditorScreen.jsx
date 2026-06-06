import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../components/ui/Icon'
import Avatar from '../components/ui/Avatar'
import { getProfiles, patchProfile, createProfile, deleteProfile } from '../services/api'

const MODEL_LABELS = {
  'claude-sonnet-4-6': 'Claude Sonnet',
  'claude-opus-4-8': 'Claude Opus',
  'claude-haiku-4-5-20251001': 'Claude Haiku',
}
const MODEL_IDS = Object.keys(MODEL_LABELS)

function VoiceSwatch({ id, on, onClick }) {
  return (
    <button className={`t-voicesw${on ? ' is-on' : ''}`} data-voice={id} onClick={onClick} aria-label={id}>
      <span className="t-voicesw-dot" />
    </button>
  )
}

function SegBtn({ on, children, onClick }) {
  return <button className={`t-seg-btn${on ? ' is-on' : ''}`} onClick={onClick}>{children}</button>
}

function TempSlider({ value, onChange }) {
  const pct = Math.round(value * 100)
  const label = value <= 0.4 ? 'centrada' : value >= 0.75 ? 'imprevisible' : 'equilibrada'
  return (
    <div className="t-temp">
      <div className="t-temp-track" style={{ position: 'relative' }}>
        <div className="t-temp-fill" style={{ width: pct + '%' }} />
        <div className="t-temp-knob" style={{ left: pct + '%' }} />
        <input
          type="range" min="0" max="1" step="0.05" value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%' }}
        />
      </div>
      <div className="t-temp-foot">
        <span>centrada</span>
        <span className="t-temp-val">{value.toFixed(2)} · {label}</span>
        <span>creativa</span>
      </div>
    </div>
  )
}

const EMPTY = { name: '', funcion: '', tipo: 'tertuliano', color: 'vera', model: 'claude-sonnet-4-6', temperature: 0.7, system_prompt: '' }

export default function EditorScreen() {
  const navigate = useNavigate()
  const [profiles, setProfiles] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getProfiles().then((ps) => {
      const active = ps.filter((p) => !p.archived)
      setProfiles(active)
      if (active.length > 0) select(active[0])
    })
  }, [])

  const select = (p) => {
    setActiveId(p.id)
    setForm({
      name: p.name,
      funcion: p.funcion,
      tipo: p.tipo,
      color: p.color ?? 'vera',
      model: p.model,
      temperature: p.temperature,
      system_prompt: p.system_prompt,
    })
    setDirty(false)
  }

  const set = (key, val) => { setForm((f) => ({ ...f, [key]: val })); setDirty(true) }

  const save = async () => {
    if (!dirty || saving) return
    setSaving(true)
    try {
      if (activeId === 'new') {
        const created = await createProfile(form)
        setProfiles((ps) => [...ps, created])
        select(created)
      } else {
        const updated = await patchProfile(activeId, form)
        setProfiles((ps) => ps.map((p) => (p.id === activeId ? updated : p)))
        setDirty(false)
      }
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!activeId || activeId === 'new') return
    if (!confirm(`¿Eliminar a ${form.name}?`)) return
    await deleteProfile(activeId)
    const remaining = profiles.filter((p) => p.id !== activeId)
    setProfiles(remaining)
    if (remaining.length > 0) select(remaining[0])
    else { setActiveId(null); setForm(EMPTY) }
  }

  const newProfile = () => {
    setActiveId('new')
    setForm(EMPTY)
    setDirty(false)
  }

  const duplicate = async () => {
    if (!activeId || activeId === 'new') return
    setSaving(true)
    try {
      const copy = await createProfile({ ...form, name: `${form.name} (copia)` })
      setProfiles((ps) => [...ps, copy])
      select(copy)
    } finally {
      setSaving(false)
    }
  }

  const active = profiles.find((p) => p.id === activeId)

  return (
    <div className="t-editor">
      <div className="t-ed-list">
        <div className="t-ed-list-head">
          <div className="t-sheet-eyebrow">Tertulianos</div>
          <button className="t-iconbtn" onClick={newProfile}><Icon d={Ico.plus} size={17} /></button>
        </div>
        <div className="t-ed-list-scroll t-scroll">
          {profiles.map((p) => (
            <div
              key={p.id}
              className={`t-ed-litem${p.id === activeId ? ' is-active' : ''}`}
              onClick={() => select(p)}
              style={{ cursor: 'pointer' }}
            >
              <Avatar profile={p} size={34} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="t-ed-litem-name" data-voice={p.color}>{p.name}</div>
                <div className="t-ed-litem-role">{p.funcion?.toLowerCase()}</div>
              </div>
              {p.tipo === 'facilitador' && <span className="t-tag-fac">fac.</span>}
            </div>
          ))}
        </div>
        <div className="t-ed-list-foot">
          <button className="t-btn is-sm is-ghost" onClick={() => navigate('/')}>
            ← Volver al chat
          </button>
        </div>
      </div>

      {activeId && (
        <div className="t-ed-form">
          <div className="t-ed-form-head">
            <Avatar profile={activeId === 'new' ? { name: form.name || '?', color: form.color } : active} size={44} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t-ed-form-title" data-voice={form.color}>{form.name || 'Nuevo perfil'}</div>
              <div className="t-rolechip">{form.funcion?.toLowerCase()} · {MODEL_LABELS[form.model] ?? form.model}</div>
            </div>
            <button className="t-btn is-sm" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>

          <div className="t-ed-form-body t-scroll">
            <div className="t-ed-grid">
              <div className="t-fld" style={{ gridColumn: 'span 7' }}>
                <div className="t-field-label">Nombre</div>
                <input className="t-input" value={form.name} onChange={(e) => set('name', e.target.value)}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }} />
              </div>
              <div className="t-fld" style={{ gridColumn: 'span 5' }}>
                <div className="t-field-label">Papel en la mesa</div>
                <div className="t-seg">
                  <SegBtn on={form.tipo === 'tertuliano'} onClick={() => set('tipo', 'tertuliano')}>Tertuliano</SegBtn>
                  <SegBtn on={form.tipo === 'facilitador'} onClick={() => set('tipo', 'facilitador')}>Facilitador</SegBtn>
                </div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Función · cómo se le presenta</div>
                <input className="t-input" value={form.funcion} onChange={(e) => set('funcion', e.target.value)}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }} />
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Color de voz</div>
                <div className="t-voicerow">
                  {['vera', 'bruno', 'iris', 'oro', 'purpura', 'gris', 'abismo', 'rojo', 'naranja'].map((v) => (
                    <VoiceSwatch key={v} id={v} on={form.color === v} onClick={() => set('color', v)} />
                  ))}
                  <span className="t-voicerow-note">El color identifica a {form.name || 'este perfil'} en el chat.</span>
                </div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 6' }}>
                <div className="t-field-label">Modelo</div>
                <select
                  className="t-select"
                  value={form.model}
                  onChange={(e) => set('model', e.target.value)}
                  style={{ width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit', cursor: 'pointer' }}
                >
                  {MODEL_IDS.map((id) => <option key={id} value={id}>{MODEL_LABELS[id]}</option>)}
                </select>
                <div className="t-fld-hint">Opus razona más hondo · Sonnet va más rápido</div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 6' }}>
                <div className="t-field-label">Temperatura</div>
                <TempSlider value={form.temperature} onChange={(v) => set('temperature', v)} />
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Cómo piensa · system prompt</div>
                <textarea
                  className="t-textarea"
                  value={form.system_prompt}
                  onChange={(e) => set('system_prompt', e.target.value)}
                  rows={8}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit', resize: 'vertical' }}
                />
              </div>
            </div>
          </div>

          <div className="t-ed-form-foot">
            {activeId !== 'new' && (
              <button className="t-btn is-sm is-ghost" style={{ color: 'var(--warn)' }} onClick={remove}>
                Eliminar
              </button>
            )}
            {activeId !== 'new' && (
              <button className="t-btn is-sm is-ghost" onClick={duplicate} disabled={saving}>
                <Icon d={Ico.copy} size={14} />Duplicar
              </button>
            )}
            <div className="t-head-spacer" />
            {dirty && <span className="t-cost">cambios sin guardar</span>}
            <button className="t-btn is-sm is-ghost" onClick={() => { if (active) select(active); else { setActiveId(null); setForm(EMPTY) } }}>
              Descartar
            </button>
            <button className="t-btn is-sm is-primary" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
