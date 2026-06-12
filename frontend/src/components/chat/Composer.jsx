import { useState, useRef } from 'react'
import Icon, { Ico } from '../ui/Icon'
import MentionPopover from './MentionPopover'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'
import { streamTurn, streamRound } from '../../services/sse'

export default function Composer() {
  const [text, setText] = useState('')
  const [mentionFilter, setMentionFilter] = useState(null)
  const inputRef = useRef(null)

  const { activeChannelId, roster } = useChannelStore()
  const { addUserMessage, addThinking, appendToken, finalizeMessage, setCost, setError } = useThreadStore()
  const isStreaming = useThreadStore((s) => s.thinking.size > 0 || s.messages.some((m) => m.streaming))

  const handlers = {
    onStart: (profileId) => addThinking(profileId),
    onToken: (profileId, chunk) => appendToken(profileId, chunk),
    onDone: (profileId, meta) => finalizeMessage(profileId, meta),
    onComplete: (total) => setCost(total),
    onError: (msg) => setError(msg),
  }

  const handleInput = (e) => {
    const val = e.target.value
    setText(val)
    const atIdx = val.lastIndexOf('@')
    if (atIdx !== -1 && atIdx === val.length - 1) {
      setMentionFilter('')
    } else if (atIdx !== -1 && !val.slice(atIdx + 1).includes(' ')) {
      setMentionFilter(val.slice(atIdx + 1))
    } else {
      setMentionFilter(null)
    }
  }

  const selectMention = (name) => {
    const atIdx = text.lastIndexOf('@')
    setText(text.slice(0, atIdx) + '@' + name + ' ')
    setMentionFilter(null)
    inputRef.current?.focus()
  }

  const send = async () => {
    if (!text.trim() || !activeChannelId || isStreaming) return
    const content = text.trim()
    setText('')
    setMentionFilter(null)
    addUserMessage(content)
    await streamTurn(activeChannelId, content, handlers)
  }

  const handleRound = async () => {
    if (!activeChannelId || isStreaming) return
    await streamRound(activeChannelId, handlers)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="t-composer">
      <div className="t-composer-inner">
        <div className="t-inputbar" style={{ position: 'relative' }}>
          {mentionFilter !== null && (
            <div style={{ position: 'absolute', bottom: '100%', left: 0, zIndex: 10 }}>
              <MentionPopover
                profiles={roster}
                filter={mentionFilter}
                onSelect={selectMention}
                onClose={() => setMentionFilter(null)}
              />
            </div>
          )}
          <div className="t-input-field">
            <textarea
              ref={inputRef}
              value={text}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Escribe… usa @ para dirigirte a alguien"
              disabled={isStreaming || !activeChannelId}
              rows={2}
              style={{
                background: 'none', border: 'none', outline: 'none',
                flex: 1, font: 'inherit', color: 'inherit', width: '100%',
                resize: 'vertical', minHeight: '2.8em', maxHeight: '12em',
                overflowY: 'auto', lineHeight: '1.4',
              }}
            />
          </div>
          <div className="t-input-actions">
            <button
              className="t-btn is-sm is-ghost"
              onClick={handleRound}
              disabled={isStreaming || !activeChannelId}
            >
              <Icon d={Ico.round} size={16} />Otra ronda
            </button>
            <button
              className="t-sendbtn"
              onClick={send}
              disabled={!text.trim() || isStreaming || !activeChannelId}
            >
              <Icon d={Ico.send} size={18} />
            </button>
          </div>
        </div>
        <div className="t-composer-hint">
          <span className="t-kbd">@</span> menciona a un tertuliano
          <span style={{ opacity: 0.5 }}> · </span>
          <span className="t-kbd">⏎</span> enviar · <span className="t-kbd">⇧⏎</span> nueva línea
          <span style={{ opacity: 0.5 }}> · </span>
          "Otra ronda" relanza sin escribir nada
        </div>
      </div>
    </div>
  )
}
