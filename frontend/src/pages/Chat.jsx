import { useEffect, useState } from 'react'
import { AlertCircle, X } from 'lucide-react'
import { useChat } from '../hooks/useChat'
import { useSettings } from '../context/SettingsContext'
import ChatSidebar from '../components/chat/ChatSidebar'
import ChatToolbar from '../components/chat/ChatToolbar'
import ChatMessages from '../components/chat/ChatMessages'
import ChatInput from '../components/chat/ChatInput'
import DocumentGroundingPanel from '../components/chat/DocumentGroundingPanel'

export default function Chat() {
  const { apiKeys } = useSettings()
  const [message, setMessage] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [docPanelCollapsed, setDocPanelCollapsed] = useState(false)

  const {
    conversations, activeConversationId, messages, isStreaming,
    streamingContent, streamingThinking, streamingCitations, error,
    modelId, setModelId, thinkingEnabled, setThinkingEnabled,
    streamingEnabled, setStreamingEnabled, temperature, setTemperature,
    selectedDocIds, setSelectedDocIds,
    loadConversations, loadConversation, createNewConversation,
    removeConversation, sendMessage, stopStreaming,
  } = useChat()

  useEffect(() => {
    document.title = 'Chat â€” Intelidoc'
    loadConversations()
  }, [loadConversations])

  const handleSend = () => {
    if (!message.trim()) return
    sendMessage(message)
    setMessage('')
  }

  const handleSuggestedPrompt = (text) => {
    setMessage(text)
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left â€” Conversation Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={loadConversation}
        onNew={createNewConversation}
        onDelete={removeConversation}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Center â€” Chat Area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Toolbar */}
        <ChatToolbar
          modelId={modelId}
          setModelId={setModelId}
          thinkingEnabled={thinkingEnabled}
          setThinkingEnabled={setThinkingEnabled}
          streamingEnabled={streamingEnabled}
          setStreamingEnabled={setStreamingEnabled}
          temperature={temperature}
          setTemperature={setTemperature}
          apiKeys={apiKeys}
        />

        {/* Error Banner */}
        {error && (
          <div className="flex items-center gap-2 mx-4 mt-2 px-4 py-2.5 rounded-xl border border-red-500/20 bg-red-500/10 animate-fade-in">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <p className="text-xs text-red-400 flex-1">{error}</p>
            <button onClick={() => {}} className="p-1 rounded-lg text-red-400/50 hover:text-red-400 transition-colors">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Messages */}
        <ChatMessages
          messages={messages}
          streamingContent={streamingContent}
          streamingThinking={streamingThinking}
          streamingCitations={streamingCitations}
          isStreaming={isStreaming}
          onSuggestedPrompt={handleSuggestedPrompt}
        />

        {/* Input */}
        <ChatInput
          message={message}
          setMessage={setMessage}
          onSend={handleSend}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          selectedDocCount={selectedDocIds.length}
        />
      </div>

      {/* Right â€” Document Grounding Panel */}
      <DocumentGroundingPanel
        selectedIds={selectedDocIds}
        setSelectedIds={setSelectedDocIds}
        collapsed={docPanelCollapsed}
        onToggle={() => setDocPanelCollapsed(!docPanelCollapsed)}
      />
    </div>
  )
}
