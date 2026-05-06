import { apiFetch } from './client'

/**
 * Chat API — Conversation & Message CRUD via backend.
 * LLM completions are called directly from the browser to cloud APIs.
 */

export async function createConversation(data, baseUrl = '') {
  return apiFetch('/v1/chat/conversations', {
    baseUrl,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function listConversations(baseUrl = '') {
  return apiFetch('/v1/chat/conversations', { baseUrl })
}

export async function getConversation(id, baseUrl = '') {
  return apiFetch(`/v1/chat/conversations/${id}`, { baseUrl })
}

export async function updateConversation(id, data, baseUrl = '') {
  return apiFetch(`/v1/chat/conversations/${id}`, {
    baseUrl,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function deleteConversation(id, baseUrl = '') {
  return apiFetch(`/v1/chat/conversations/${id}`, {
    baseUrl,
    method: 'DELETE',
  })
}

export async function addMessage(conversationId, data, baseUrl = '') {
  return apiFetch(`/v1/chat/conversations/${conversationId}/messages`, {
    baseUrl,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

/**
 * Stream an OpenAI-compatible chat completion directly from the browser.
 * Returns an async iterator of delta content strings.
 */
export async function* streamOpenAICompletion(messages, config) {
  const { apiKey, apiBase, model, temperature = 0.7, thinkingEnabled = false } = config

  const base = (apiBase || 'https://api.openai.com/v1').replace(/\/+$/, '')
  const url = `${base}/chat/completions`

  const systemMessages = thinkingEnabled
    ? [
        {
          role: 'system',
          content:
            'You are a helpful document analysis assistant. When reasoning through complex questions, wrap your thinking process in <think>...</think> tags before providing your final answer. Always cite sources using [1], [2], etc. when referencing specific documents.',
        },
      ]
    : [
        {
          role: 'system',
          content:
            'You are a helpful document analysis assistant. Always cite sources using [1], [2], etc. when referencing specific documents provided as context.',
        },
      ]

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
      ...(apiBase ? { 'api-key': apiKey } : {}),
    },
    body: JSON.stringify({
      model: model || 'gpt-4o',
      messages: [...systemMessages, ...messages],
      temperature,
      stream: true,
      max_tokens: 4096,
    }),
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`OpenAI API error ${response.status}: ${err}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue
      const data = trimmed.slice(6)
      if (data === '[DONE]') return

      try {
        const parsed = JSON.parse(data)
        const delta = parsed.choices?.[0]?.delta?.content
        if (delta) yield { content: delta, usage: parsed.usage }
      } catch {
        // skip malformed JSON chunks
      }
    }
  }
}

/**
 * Stream a Google Gemini chat completion directly from the browser.
 */
export async function* streamGeminiCompletion(messages, config) {
  const { apiKey, model = 'gemini-2.0-flash', temperature = 0.7, thinkingEnabled = false } = config

  const systemInstruction = thinkingEnabled
    ? 'You are a helpful document analysis assistant. When reasoning through complex questions, wrap your thinking process in <think>...</think> tags before providing your final answer. Always cite sources using [1], [2], etc. when referencing specific documents.'
    : 'You are a helpful document analysis assistant. Always cite sources using [1], [2], etc. when referencing specific documents provided as context.'

  const geminiMessages = messages.map((m) => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }],
  }))

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${apiKey}`

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: systemInstruction }] },
      contents: geminiMessages,
      generationConfig: { temperature, maxOutputTokens: 4096 },
    }),
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Gemini API error ${response.status}: ${err}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue
      const data = trimmed.slice(6)

      try {
        const parsed = JSON.parse(data)
        const text = parsed.candidates?.[0]?.content?.parts?.[0]?.text
        if (text) {
          yield {
            content: text,
            usage: parsed.usageMetadata
              ? {
                  prompt_tokens: parsed.usageMetadata.promptTokenCount,
                  completion_tokens: parsed.usageMetadata.candidatesTokenCount,
                  total_tokens: parsed.usageMetadata.totalTokenCount,
                }
              : null,
          }
        }
      } catch {
        // skip
      }
    }
  }
}
