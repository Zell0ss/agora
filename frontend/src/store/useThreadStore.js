import { create } from 'zustand'

export const useThreadStore = create((set) => ({
  messages: [],
  thinking: new Set(),
  accumulatedCost: '0',
  error: null,

  setMessages: (messages) => set({ messages }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: `user-${Date.now()}`,
          role: 'human',
          profileId: null,
          content,
          time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
          streaming: false,
          costUsd: null,
        },
      ],
    })),

  addThinking: (profileId) =>
    set((s) => ({ thinking: new Set([...s.thinking, profileId]) })),

  appendToken: (profileId, chunk) =>
    set((s) => {
      const existing = s.messages.find((m) => m.profileId === profileId && m.streaming)
      if (existing) {
        return {
          messages: s.messages.map((m) =>
            m.profileId === profileId && m.streaming
              ? { ...m, content: m.content + chunk }
              : m
          ),
        }
      }
      return {
        messages: [
          ...s.messages,
          {
            id: `stream-${profileId}-${Date.now()}`,
            role: 'persona',
            profileId,
            content: chunk,
            time: null,
            streaming: true,
            costUsd: null,
          },
        ],
      }
    }),

  finalizeMessage: (profileId, meta) =>
    set((s) => ({
      thinking: new Set([...s.thinking].filter((id) => id !== profileId)),
      messages: s.messages.map((m) =>
        m.profileId === profileId && m.streaming
          ? {
              ...m,
              streaming: false,
              time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
              costUsd: meta.costUsd,
            }
          : m
      ),
    })),

  setCost: (total) => set({ accumulatedCost: total, error: null }),
  setError: (msg) => set({ error: msg }),
  clearError: () => set({ error: null }),
}))
