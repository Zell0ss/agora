import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from './store/useAppStore'
import { useChannelStore } from './store/useChannelStore'
import ChatScreen from './screens/ChatScreen'
import CreateScreen from './screens/CreateScreen'
import EditorScreen from './screens/EditorScreen'

export default function App() {
  const theme = useAppStore((s) => s.theme)
  const fetchChannels = useChannelStore((s) => s.fetchChannels)

  useEffect(() => {
    document.documentElement.classList.toggle('t-dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    fetchChannels()
  }, [fetchChannels])

  return (
    <div className={`t${theme === 'dark' ? ' t-dark' : ''}`} style={{ height: '100vh', overflow: 'hidden' }}>
      <Routes>
        <Route path="/" element={<ChatScreen />} />
        <Route path="/channels/new" element={<CreateScreen />} />
        <Route path="/profiles" element={<EditorScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
