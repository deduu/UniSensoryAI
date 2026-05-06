import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check } from 'lucide-react'
import { useState, useCallback } from 'react'

function CodeBlock({ children, className, ...props }) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  if (!match) {
    return (
      <code
        className="rounded bg-surface-muted px-1.5 py-0.5 text-[13px] font-mono text-brand-hover"
        {...props}
      >
        {children}
      </code>
    )
  }

  return (
    <div className="group relative my-3 rounded-xl overflow-hidden border border-surface-border">
      <div className="flex items-center justify-between bg-surface-muted/80 px-4 py-2 text-xs text-ink-muted">
        <span className="font-mono">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" /> Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" /> Copy
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: '1rem',
          fontSize: '13px',
          background: '#1a1a2e',
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

export default function MarkdownRenderer({ content }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none 
                    prose-headings:text-ink prose-headings:font-semibold
                    prose-p:text-ink/90 prose-p:leading-relaxed
                    prose-a:text-brand-hover prose-a:no-underline hover:prose-a:underline
                    prose-strong:text-ink prose-strong:font-semibold
                    prose-li:text-ink/90
                    prose-blockquote:border-brand/40 prose-blockquote:text-ink-muted
                    prose-hr:border-surface-border
                    prose-table:text-sm
                    prose-th:text-ink prose-th:bg-surface-muted/50 prose-th:px-3 prose-th:py-2
                    prose-td:px-3 prose-td:py-2 prose-td:border-surface-border">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: CodeBlock,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
