export function parseSSEChunk(text, leftover, onEvent) {
  const combined = leftover + text
  const parts = combined.split('\n\n')
  const remaining = parts.pop()

  for (const part of parts) {
    for (const line of part.split('\n')) {
      if (!line.startsWith('data: ')) continue
      const json = line.slice(6).trim()
      if (!json) continue
      try {
        onEvent(JSON.parse(json))
      } catch {
        // malformed JSON — skip
      }
    }
  }
  return remaining
}

async function consumeStream(body, onEvent) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let leftover = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    leftover = parseSSEChunk(decoder.decode(value, { stream: true }), leftover, onEvent)
  }
}

function dispatchEvent(evt, { onStart, onToken, onDone, onComplete }) {
  switch (evt.type) {
    case 'start':
      onStart(evt.profile_id, evt.profile_name)
      break
    case 'token':
      onToken(evt.profile_id, evt.token)
      break
    case 'done':
      onDone(evt.profile_id, {
        tokensIn: evt.tokens_in,
        tokensOut: evt.tokens_out,
        costUsd: evt.cost_usd,
      })
      break
    case 'TURN_COMPLETE':
      onComplete(evt.total_cost_usd)
      break
  }
}

export async function streamTurn(channelId, content, handlers) {
  const { onError } = handlers
  try {
    const resp = await fetch(`/api/channels/${channelId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await consumeStream(resp.body, (evt) => dispatchEvent(evt, handlers))
  } catch (err) {
    onError(err.message)
  }
}

export async function streamRound(channelId, handlers) {
  const { onError } = handlers
  try {
    const resp = await fetch(`/api/channels/${channelId}/rounds`, { method: 'POST' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await consumeStream(resp.body, (evt) => dispatchEvent(evt, handlers))
  } catch (err) {
    onError(err.message)
  }
}
