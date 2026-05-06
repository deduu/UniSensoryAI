import { useState, useCallback, useRef } from 'react'
import { useApp } from '../context/AppContext'
import { useSettings } from '../context/SettingsContext'
import { useDocuments } from './useDocuments'
import {
  createConversation, listConversations, getConversation,
  updateConversation, deleteConversation, addMessage,
  streamOpenAICompletion, streamGeminiCompletion,
} from '../api/chat'
import { AVAILABLE_MODELS } from '../api/models'

export function useChat() {
  const { backendUrl } = useApp()
  const { apiKeys } = useSettings()
  const { allDocuments } = useDocuments()

  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingThinking, setStreamingThinking] = useState('')
  const [error, setError] = useState(null)

  // Chat config
  const [modelId, setModelId] = useState('gpt-4o')
  const [thinkingEnabled, setThinkingEnabled] = useState(false)
  const [streamingEnabled, setStreamingEnabled] = useState(true)
  const [temperature, setTemperature] = useState(0.7)
  const [selectedDocIds, setSelectedDocIds] = useState([])

  const abortRef = useRef(null)

  // Load conversations from backend
  const loadConversations = useCallback(async () => {
    try {
      const data = await listConversations(backendUrl)
      setConversations(data)
    } catch (err) {
      console.error('Failed to load conversations:', err)
    }
  }, [backendUrl])

  // Load a specific conversation with messages
  const loadConversation = useCallback(async (id) => {
    try {
      const data = await getConversation(id, backendUrl)
      setActiveConversationId(id)
      setMessages(data.messages || [])
      setModelId(data.model_id || 'gpt-4o')
      setThinkingEnabled(data.thinking_enabled || false)
      setStreamingEnabled(data.streaming_enabled !== false)
      setTemperature(data.temperature || 0.7)
      setSelectedDocIds(data.grounded_document_ids || [])
    } catch (err) {
      console.error('Failed to load conversation:', err)
      setError('Failed to load conversation')
    }
  }, [backendUrl])

  // Create new conversation
  const createNewConversation = useCallback(async () => {
    try {
      const data = await createConversation({
        title: 'New conversation',
        model_id: modelId,
        temperature,
        thinking_enabled: thinkingEnabled,
        streaming_enabled: streamingEnabled,
        grounded_document_ids: selectedDocIds,
      }, backendUrl)
      setActiveConversationId(data.id)
      setMessages([])
      await loadConversations()
      return data.id
    } catch (err) {
      console.error('Failed to create conversation:', err)
      setError('Failed to create conversation')
      return null
    }
  }, [backendUrl, modelId, temperature, thinkingEnabled, streamingEnabled, selectedDocIds, loadConversations])

  // Delete conversation
  const removeConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id, backendUrl)
      if (activeConversationId === id) {
        setActiveConversationId(null)
        setMessages([])
      }
      await loadConversations()
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }, [backendUrl, activeConversationId, loadConversations])

  // Build document context for grounding
  const buildDocContext = useCallback(() => {
    if (selectedDocIds.length === 0) return ''
    const parts = []
    selectedDocIds.forEach((docId, i) => {
      const doc = allDocuments.find((d) => d.id === docId)
      if (doc && doc.content_text) {
        const text = doc.content_text.length > 8000 ? doc.content_text.slice(0, 8000) + '...' : doc.content_text
        parts.push(`[Document ${i + 1}: ${doc.filename}]\n${text}`)
      }
    })
    if (parts.length === 0) return ''
    return '\n\n--- DOCUMENT CONTEXT ---\n' + parts.join('\n\n') + '\n--- END CONTEXT ---\n\n'
  }, [selectedDocIds, allDocuments])

  // Build citations from selected docs
  const buildCitations = useCallback(() => {
    return selectedDocIds.map((docId) => {
      const doc = allDocuments.find((d) => d.id === docId)
      return {
        doc_id: docId,
        filename: doc?.filename || 'Unknown',
        excerpt: doc?.content_text?.slice(0, 200) || '',
      }
    }).filter((c) => c.filename)
  }, [selectedDocIds, allDocuments])

  // Parse thinking content from response
  const parseThinking = (text) => {
    const match = text.match(/<think>([\s\S]*?)<\/think>/)
    if (match) {
      const thinking = match[1].trim()
      const content = text.replace(/<think>[\s\S]*?<\/think>/, '').trim()
      return { thinking, content }
    }
    return { thinking: '', content: text }
  }

  // Send message
  const sendMessage = useCallback(async (content) => {
    if (!content.trim() || isStreaming) return
    setError(null)

    let convId = activeConversationId
    if (!convId) {
      convId = await createNewConversation()
      if (!convId) return
    }

    // Save user message to backend
    const userMsg = await addMessage(convId, { role: 'user', content }, backendUrl)
    const newUserMsg = { ...userMsg, role: 'user', content }
    setMessages((prev) => [...prev, newUserMsg])

    // Update conversation title from first message
    if (messages.length === 0) {
      const title = content.length > 50 ? content.slice(0, 50) + '...' : content
      await updateConversation(convId, { title }, backendUrl)
      loadConversations()
    }

    // Prepare messages for LLM
    const docContext = buildDocContext()
    const llmMessages = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: docContext + content },
    ]

    const model = AVAILABLE_MODELS.find((m) => m.id === modelId)
    const startTime = Date.now()
    let fullContent = ''
    let fullThinking = ''
    let lastUsage = null

    setIsStreaming(true)
    setStreamingContent('')
    setStreamingThinking('')

    try {
      const config = {
        model: modelId,
        temperature,
        thinkingEnabled,
      }

      let stream
      if (model?.provider === 'google') {
        config.apiKey = apiKeys.GOOGLE_API_KEY
        stream = streamGeminiCompletion(llmMessages, config)
      } else {
        config.apiKey = apiKeys.OPENAI_API_KEY
        config.apiBase = apiKeys.OPENAI_API_BASE
        stream = streamOpenAICompletion(llmMessages, config)
      }

      const controller = new AbortController()
      abortRef.current = controller

      for await (const chunk of stream) {
        if (controller.signal.aborted) break
        fullContent += chunk.content
        if (chunk.usage) lastUsage = chunk.usage

        // Parse thinking during streaming
        if (thinkingEnabled) {
          const parsed = parseThinking(fullContent)
          setStreamingThinking(parsed.thinking)
          setStreamingContent(parsed.content)
        } else {
          setStreamingContent(fullContent)
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message)
        fullContent = fullContent || `Error: ${err.message}`
      }
    }

    const latencyMs = Date.now() - startTime
    const parsed = thinkingEnabled ? parseThinking(fullContent) : { thinking: '', content: fullContent }
    const citations = buildCitations()

    // Save assistant message to backend
    try {
      const assistantMsg = await addMessage(convId, {
        role: 'assistant',
        content: parsed.content,
        thinking_content: parsed.thinking || null,
        prompt_tokens: lastUsage?.prompt_tokens || null,
        completion_tokens: lastUsage?.completion_tokens || null,
        total_tokens: lastUsage?.total_tokens || null,
        latency_ms: latencyMs,
        model_used: modelId,
        citations: citations.length > 0 ? citations : null,
      }, backendUrl)

      setMessages((prev) => [...prev, {
        ...assistantMsg,
        role: 'assistant',
        content: parsed.content,
        thinking_content: parsed.thinking || null,
        prompt_tokens: lastUsage?.prompt_tokens || null,
        completion_tokens: lastUsage?.completion_tokens || null,
        total_tokens: lastUsage?.total_tokens || null,
        latency_ms: latencyMs,
        model_used: modelId,
        citations: citations.length > 0 ? citations : null,
      }])
    } catch (err) {
      console.error('Failed to save assistant message:', err)
      // Still show the message even if save fails
      setMessages((prev) => [...prev, {
        id: 'temp-' + Date.now(),
        role: 'assistant',
        content: parsed.content,
        thinking_content: parsed.thinking || null,
        latency_ms: latencyMs,
        model_used: modelId,
        citations: citations.length > 0 ? citations : null,
        created_at: new Date().toISOString(),
      }])
    }

    setIsStreaming(false)
    setStreamingContent('')
    setStreamingThinking('')
    abortRef.current = null
  }, [activeConversationId, messages, modelId, temperature, thinkingEnabled, isStreaming, backendUrl, apiKeys, buildDocContext, buildCitations, createNewConversation, loadConversations])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  return {
    conversations, activeConversationId, messages, isStreaming,
    streamingContent, streamingThinking, error,
    modelId, setModelId, thinkingEnabled, setThinkingEnabled,
    streamingEnabled, setStreamingEnabled, temperature, setTemperature,
    selectedDocIds, setSelectedDocIds,
    loadConversations, loadConversation, createNewConversation,
    removeConversation, sendMessage, stopStreaming,
    setActiveConversationId,
  }
}
