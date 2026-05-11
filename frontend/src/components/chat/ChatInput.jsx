import { useRef, useEffect, useCallback } from 'react'
import { Send, Paperclip, Square } from 'lucide-react'

export default function ChatInput({
  message,
  setMessage,
  onSend,
  onStop,
  isStreaming = false,
  selectedDocCount = 0,
  disabled = false,
}) {
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }, [message])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (!isStreaming && message.trim()) onSend()
      }
    },
    [isStreaming, message, onSend]
  )

  return (
    <div className="shrink-0 bg-surface/30 backdrop-blur-sm p-4">
      <div className="relative flex items-end gap-3 rounded-2xl border border-surface-border bg-surface-muted/50 px-4 py-3 
                      focus-within:border-brand/40 focus-within:shadow-[0_0_15px_rgba(99,102,241,0.1)] transition-all duration-300">
        {/* Doc count indicator */}
        {selectedDocCount > 0 && (
          <div className="flex items-center gap-1.5 self-center shrink-0">
            <div className="flex items-center gap-1 rounded-lg bg-brand/15 px-2 py-1 text-[11px] font-medium text-brand-hover">
              <Paperclip className="h-3 w-3" />
              {selectedDocCount}
            </div>
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your documents..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-ink placeholder:text-ink-faint 
                     focus:outline-none disabled:opacity-50 leading-relaxed
                     scrollbar-thin scrollbar-thumb-surface-border"
          style={{ maxHeight: '180px' }}
        />

        {/* Send / Stop button */}
        {isStreaming ? (
          <button
            onClick={onStop}
            className="shrink-0 flex items-center justify-center h-9 w-9 rounded-xl 
                       bg-red-500/20 text-red-400 border border-red-500/30
                       hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.2)]
                       transition-all duration-200"
            title="Stop generating"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        ) : (
          <button
            onClick={onSend}
            disabled={!message.trim() || disabled}
            className="shrink-0 flex items-center justify-center h-9 w-9 rounded-xl 
                       bg-brand text-white shadow-[0_0_10px_rgba(99,102,241,0.2)]
                       hover:bg-brand-hover hover:shadow-glow hover:-translate-y-0.5
                       disabled:opacity-30 disabled:hover:translate-y-0 disabled:hover:shadow-none disabled:cursor-not-allowed
                       transition-all duration-200"
            title="Send message (Enter)"
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Footer hint */}
      <div className="flex items-center justify-between mt-2 px-1">
        <span className="text-[11px] text-ink-faint">
          {isStreaming ? (
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse" />
              Generating response...
            </span>
          ) : (
            'Enter to send · Shift+Enter for new line'
          )}
        </span>
        {message.length > 0 && (
          <span className="text-[11px] text-ink-faint">{message.length} chars</span>
        )}
      </div>
    </div>
  )
}
