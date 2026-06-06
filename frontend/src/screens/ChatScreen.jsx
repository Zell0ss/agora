import { useState } from 'react'
import Sidebar from '../components/chat/Sidebar'
import ChatHeader from '../components/chat/ChatHeader'
import Thread from '../components/chat/Thread'
import Composer from '../components/chat/Composer'
import ExportModal from '../components/export/ExportModal'
import { useThreadStore } from '../store/useThreadStore'

export default function ChatScreen() {
  const [showExport, setShowExport] = useState(false)
  const error = useThreadStore((s) => s.error)
  const clearError = useThreadStore((s) => s.clearError)

  return (
    <div className="t-app">
      <Sidebar />
      <main className="t-main">
        <ChatHeader onExport={() => setShowExport(true)} />
        {error && (
          <div className="t-error">
            <span>{error}</span>
            <button className="t-btn is-sm" onClick={clearError}>Reintentar</button>
          </div>
        )}
        <Thread />
        <Composer />
      </main>
      {showExport && <ExportModal onClose={() => setShowExport(false)} />}
    </div>
  )
}
