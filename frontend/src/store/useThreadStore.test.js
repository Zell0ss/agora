import { describe, it, expect, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useThreadStore } from './useThreadStore'

const INITIAL = { messages: [], thinking: new Set(), accumulatedCost: '0', error: null }

describe('useThreadStore', () => {
  beforeEach(() => useThreadStore.setState(INITIAL))

  it('addUserMessage appends a human message', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addUserMessage('Hola'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].role).toBe('human')
    expect(result.current.messages[0].content).toBe('Hola')
  })

  it('addThinking adds profileId to thinking set', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addThinking(42))
    expect(result.current.thinking.has(42)).toBe(true)
  })

  it('appendToken creates streaming message on first call', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.appendToken(1, 'Hola'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].streaming).toBe(true)
    expect(result.current.messages[0].content).toBe('Hola')
  })

  it('appendToken accumulates tokens on subsequent calls', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.appendToken(1, 'Hola'))
    act(() => result.current.appendToken(1, ' mundo'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].content).toBe('Hola mundo')
  })

  it('finalizeMessage clears streaming flag and removes from thinking', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addThinking(1))
    act(() => result.current.appendToken(1, 'Texto'))
    act(() => result.current.finalizeMessage(1, { costUsd: '0.0001' }))
    expect(result.current.thinking.has(1)).toBe(false)
    expect(result.current.messages[0].streaming).toBe(false)
    expect(result.current.messages[0].costUsd).toBe('0.0001')
  })

  it('setCost updates accumulatedCost and clears error', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => { result.current.setError('boom'); result.current.setCost('0.05') })
    expect(result.current.accumulatedCost).toBe('0.05')
    expect(result.current.error).toBeNull()
  })
})
