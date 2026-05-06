import { useRef, useEffect, useState } from 'react'
import { Bot, User, ChevronDown, Brain, Sparkles, MessageSquare, FileText, ArrowRight } from 'lucide-react'
import MarkdownRenderer from './MarkdownRenderer'
import ChatMetrics from './ChatMetrics'
import CitationBadge from './CitationBadge'

function ThinkingBlock({ content }) {
  const [expanded, setExpanded] = useState(false)
  if (!content) return null

  return (
    <div className="mb-3">
      <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-2 text-[11px] font-medium text-purple-400/80 hover:text-purple-400 transition-colors">
        <Brain className="h-3.5 w-3.5" />
        <span>{expanded ? 'Hide' : 'Show'} reasoning</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="mt-2 rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 animate-fade-in">
          <div className="text-xs text-purple-300/80 font-mono leading-relaxed whitespace-pre-wrap">{content}</div>
        </div>
      )}
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'

  // Parse citations from content — look for [1], [2], etc.
  const renderContentWithCitations = (content, citations) => {
    if (!citations || citations.length === 0) {
      return <MarkdownRenderer content={content} />
    }

    // We render markdown normally, citations are rendered as separate badges below
    return <MarkdownRenderer content={content} />
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} animate-slide-up-fade`}>
      {/* Avatar */}
      <div className={`shrink-0 flex items-center justify-center h-8 w-8 rounded-xl ${isUser ? 'bg-brand/20' : 'bg-cyan-500/15'}`}>
        {isUser ? <User className="h-4 w-4 text-brand-hover" /> : <Bot className="h-4 w-4 text-cyan-400" />}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 max-w-[85%] ${isUser ? 'flex flex-col items-end' : ''}`}>
        <div className={`rounded-2xl px-4 py-3 ${isUser ? 'bg-brand/15 border border-brand/20' : 'bg-surface-muted/50 border border-surface-border/50'}`}>
          {isAssistant && message.thinking_content && <ThinkingBlock content={message.thinking_content} />}
          {renderContentWithCitations(message.content, message.citations)}
        </div>

        {/* Citations list */}
        {isAssistant && message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2 px-1">
            <span className="text-[10px] text-ink-faint mr-1">Sources:</span>
            {message.citations.map((cite, i) => (
              <CitationBadge key={i} index={i + 1} citation={cite} />
            ))}
          </div>
        )}

        {/* Metrics */}
        {isAssistant && (message.latency_ms || message.total_tokens) && (
          <div className="px-1">
            <ChatMetrics metrics={message} />
          </div>
        )}

        {/* Timestamp */}
        <p className={`text-[10px] text-ink-faint mt-1.5 px-1 ${isUser ? 'text-right' : ''}`}>
          {message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
        </p>
      </div>
    </div>
  )
}

function StreamingMessage({ content, thinkingContent }) {
  return (
    <div className="flex gap-3 animate-slide-up-fade">
      <div className="shrink-0 flex items-center justify-center h-8 w-8 rounded-xl bg-cyan-500/15">
        <Bot className="h-4 w-4 text-cyan-400" />
      </div>
      <div className="flex-1 min-w-0 max-w-[85%]">
        <div className="rounded-2xl px-4 py-3 bg-surface-muted/50 border border-surface-border/50">
          {thinkingContent && <ThinkingBlock content={thinkingContent} />}
          {content ? (
            <MarkdownRenderer content={content} />
          ) : (
            <div className="flex items-center gap-1.5">
              <div className="flex gap-1">
                <span className="h-2 w-2 rounded-full bg-brand animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-2 w-2 rounded-full bg-brand animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-2 w-2 rounded-full bg-brand animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          {content && <span className="inline-block w-0.5 h-4 bg-brand animate-pulse ml-0.5 align-text-bottom" />}
        </div>
      </div>
    </div>
  )
}

const SUGGESTED_PROMPTS = [
  { icon: FileText, text: 'Summarize the key findings in my documents' },
  { icon: Sparkles, text: 'Extract the main data points and tables' },
  { icon: ArrowRight, text: 'Compare insights across uploaded files' },
]

export default function ChatMessages({ messages, streamingContent, streamingThinking, isStreaming, onSuggestedPrompt }) {
  const scrollRef = useRef(null)
  const bottomRef = useRef(null)
  const [showScrollBtn, setShowScrollBtn] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    setShowScrollBtn(!atBottom)
  }

  const scrollToBottom = () => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })

  // Empty state
  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="relative">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand/20 to-cyan-500/20 border border-brand/20">
            <MessageSquare className="h-8 w-8 text-brand" />
          </div>
          <div className="absolute -inset-3 rounded-3xl bg-brand/5 blur-xl -z-10" />
        </div>
        <h2 className="mt-5 text-lg font-semibold text-ink">Chat with your documents</h2>
        <p className="mt-1.5 max-w-sm text-center text-sm text-ink-muted">
          Ask questions about your processed documents. Select documents from the right panel to ground responses.
        </p>
        <div className="mt-8 grid gap-2.5 w-full max-w-md">
          {SUGGESTED_PROMPTS.map((prompt, i) => (
            <button key={i} onClick={() => onSuggestedPrompt(prompt.text)} className="flex items-center gap-3 rounded-xl border border-surface-border/50 bg-surface-muted/30 px-4 py-3 text-left hover:bg-surface-subtle hover:border-brand/20 transition-all duration-200 group">
              <prompt.icon className="h-4 w-4 text-ink-faint group-hover:text-brand transition-colors shrink-0" />
              <span className="text-sm text-ink-muted group-hover:text-ink transition-colors">{prompt.text}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex-1 overflow-hidden">
      <div ref={scrollRef} onScroll={handleScroll} className="h-full overflow-y-auto px-6 py-6 space-y-6">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && <StreamingMessage content={streamingContent} thinkingContent={streamingThinking} />}
        <div ref={bottomRef} />
      </div>

      {showScrollBtn && (
        <button onClick={scrollToBottom} className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full bg-surface-muted/90 border border-surface-border px-3 py-1.5 text-xs text-ink-muted backdrop-blur-sm hover:bg-surface-subtle hover:text-ink transition-all shadow-card animate-fade-in">
          <ChevronDown className="h-3.5 w-3.5" /> Scroll to bottom
        </button>
      )}
    </div>
  )
}
