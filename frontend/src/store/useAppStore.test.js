import { describe, it, expect, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useAppStore } from './useAppStore'

describe('useAppStore', () => {
  beforeEach(() => useAppStore.setState({ theme: 'light' }))

  it('starts with light theme', () => {
    const { result } = renderHook(() => useAppStore())
    expect(result.current.theme).toBe('light')
  })

  it('toggleTheme switches to dark', () => {
    const { result } = renderHook(() => useAppStore())
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('dark')
  })

  it('toggleTheme switches back to light', () => {
    useAppStore.setState({ theme: 'dark' })
    const { result } = renderHook(() => useAppStore())
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('light')
  })
})
