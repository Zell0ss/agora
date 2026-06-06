import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Icon, { Ico } from '../ui/Icon'
import { useChannelStore } from '../../store/useChannelStore'
import { parseSSEChunk } from '../../services/sse'

export default function SynthesisModal({ onClose }) {
  const { channels, activeChannelId } = useChannelStore()
  const channel = channels.find((c) => c.id === activeChannelId)

  const [markdown, setMarkdown] = useState('')
  const [status, setStatus] = useState('loading') // loading | streaming | done | error
  const [errorMsg, setErrorMsg] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!activeChannelId) return
    let cancelled = false

    async function fetchSynthesis() {
      try {
        const resp = await fetch(`/api/channels/${activeChannelId}/synthesize`, { method: 'POST' })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let leftover = ''

        const onEvent = (evt) => {
          if (cancelled) return
          if (evt.type === 'start') {
            setStatus('streaming')
          } else if (evt.type === 'token') {
            setMarkdown((s) => s + evt.token)
          } else if (evt.type === 'done') {
            setStatus('done')
          } else if (evt.type === 'error') {
            setErrorMsg(evt.message || 'Error desconocido')
            setStatus('error')
          }
        }

        while (true) {
          const { done, value } = await reader.read()
          if (done || cancelled) break
          leftover = parseSSEChunk(decoder.decode(value, { stream: true }), leftover, onEvent)
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMsg(err.message)
          setStatus('error')
        }
      }
    }

    fetchSynthesis()
    return () => { cancelled = true }
  }, [activeChannelId])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(markdown)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = markdown
      ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0'
      document.body.appendChild(ta)
      ta.focus(); ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const download = () => {
    const slug = (channel?.title || 'tertulia').toLowerCase().replace(/\s+/g, '-')
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${slug}-sintesis.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="t-modal-backdrop" onClick={onClose}>
      <div className="t-modal t-synth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="t-modal-head">
          <div>
            <div className="t-sheet-eyebrow">Agora · Moderador</div>
            <div className="t-modal-title">Síntesis</div>
          </div>
          <div className="t-head-spacer" />
          <button className="t-iconbtn" onClick={onClose}>✕</button>
        </div>

        {(status === 'done' || status === 'streaming') && markdown && (
          <div className="t-modal-bar">
            <span className="t-modal-hint">
              {status === 'streaming' ? 'Generando…' : 'Listo · copia o descarga el .md'}
            </span>
            <div className="t-head-spacer" />
            <button className="t-btn is-sm" onClick={download} disabled={status === 'streaming'}>
              <Icon d={Ico.download} size={15} />Descargar .md
            </button>
            <button className="t-btn is-sm is-primary" onClick={copy} disabled={status === 'streaming'}>
              <Icon d={Ico.copy} size={15} />{copied ? '✓ Copiado' : 'Copiar'}
            </button>
          </div>
        )}

        <div className="t-modal-body t-scroll">
          {status === 'loading' && (
            <div className="t-synth-loading">
              <div className="t-think-typing">
                <span /><span /><span />
              </div>
              <span>El Moderador está leyendo la tertulia…</span>
            </div>
          )}
          {status === 'error' && (
            <div className="t-synth-error">
              <Icon d={Ico.warn} size={20} />
              <span>{errorMsg}</span>
            </div>
          )}
          {(status === 'streaming' || status === 'done') && markdown && (
            <div className="t-md-msg t-synth-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
              {status === 'streaming' && <span className="t-caret" />}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
