import { describe, it, expect } from 'vitest'
import { parseSSEChunk } from './sse'

describe('parseSSEChunk', () => {
  it('parses a complete data line', () => {
    const events = []
    const leftover = parseSSEChunk(
      'data: {"type":"token","profile_id":1,"token":"Hola"}\n\n',
      '',
      (e) => events.push(e)
    )
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('token')
    expect(events[0].token).toBe('Hola')
    expect(leftover).toBe('')
  })

  it('handles chunks split across boundaries', () => {
    const events = []
    const partial = parseSSEChunk('data: {"type":"star', '', (e) => events.push(e))
    expect(events).toHaveLength(0)
    const leftover = parseSSEChunk('t","profile_id":1}\n\n', partial, (e) => events.push(e))
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('start')
    expect(leftover).toBe('')
  })

  it('parses multiple events in one chunk', () => {
    const events = []
    parseSSEChunk(
      'data: {"type":"start","profile_id":1}\n\ndata: {"type":"token","profile_id":1,"token":"A"}\n\n',
      '',
      (e) => events.push(e)
    )
    expect(events).toHaveLength(2)
    expect(events[0].type).toBe('start')
    expect(events[1].type).toBe('token')
  })

  it('ignores empty data lines', () => {
    const events = []
    parseSSEChunk('data: \n\n', '', (e) => events.push(e))
    expect(events).toHaveLength(0)
  })
})
