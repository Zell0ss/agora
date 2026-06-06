import { create } from 'zustand'
import { getChannels, getRoster, getChannelMessages, getProfiles } from '../services/api'
import { useThreadStore } from './useThreadStore'

export const useChannelStore = create((set, get) => ({
  channels: [],
  activeChannelId: null,
  roster: [],

  fetchChannels: async () => {
    const channels = await getChannels()
    set({ channels })
  },

  setActive: async (channelId) => {
    set({ activeChannelId: channelId, roster: [] })
    useThreadStore.getState().setMessages([])

    try {
      const [rosterEntries, allProfiles, rawMessages] = await Promise.all([
        getRoster(channelId),
        getProfiles(),
        getChannelMessages(channelId),
      ])

      // Discard stale results if user switched channels while fetching
      if (get().activeChannelId !== channelId) return

      const profileMap = Object.fromEntries(allProfiles.map((p) => [p.id, p]))
      const roster = rosterEntries.map((entry) => ({
        ...profileMap[entry.profile_id],
        ...entry,
      }))

      const messages = rawMessages.map((m) => ({
        id: m.id,
        role: m.role,
        profileId: m.profile_id,
        content: m.content,
        time: new Date(m.created_at).toLocaleTimeString('es', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        streaming: false,
        costUsd: m.cost_usd ? String(m.cost_usd) : null,
      }))

      set({ roster })
      useThreadStore.getState().setMessages(messages)
    } catch (err) {
      useThreadStore.getState().setError('Error al cargar el canal. ¿Reintentar?')
    }
  },

  addChannel: (channel) =>
    set((s) => ({ channels: [channel, ...s.channels] })),
}))
