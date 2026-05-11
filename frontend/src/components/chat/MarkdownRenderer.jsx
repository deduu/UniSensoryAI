import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check } from 'lucide-react'
import { Children, useState, useCallback, useMemo } from 'react'
import CitationBadge from './CitationBadge'

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

// Split a string into [text, <CitationBadge/>, text, ...] based on [N] markers.
// Returns the original string when no valid markers are present.
function splitTextOnCitations(text, citations, keyPrefix) {
  if (typeof text !== 'string') return text
  if (!citations || citations.length === 0 || !text.includes('[')) return text

  const regex = /\[(\d+)\]/g
  const out = []
  let lastIndex = 0
  let match
  let i = 0
  while ((match = regex.exec(text)) !== null) {
    const n = parseInt(match[1], 10)
    if (n < 1 || n > citations.length) continue
    if (match.index > lastIndex) out.push(text.slice(lastIndex, match.index))
    out.push(
      <CitationBadge
        key={`${keyPrefix}-${i++}`}
        index={n}
        citation={citations[n - 1]}
      />
    )
    lastIndex = match.index + match[0].length
  }
  if (out.length === 0) return text
  if (lastIndex < text.length) out.push(text.slice(lastIndex))
  return out
}

function processChildren(children, citations, keyPrefix) {
  if (!citations || citations.length === 0) return children
  return Children.map(children, (child, idx) => {
    if (typeof child === 'string') {
      return splitTextOnCitations(child, citations, `${keyPrefix}-${idx}`)
    }
    return child
  })
}

export default function MarkdownRenderer({ content, citations }) {
  const components = useMemo(() => {
    const wrap = (Tag, key) => function CitationWrap({ node, children, ...props }) {
      return <Tag {...props}>{processChildren(children, citations, key)}</Tag>
    }
    return {
      code: CodeBlock,
      p: wrap('p', 'p'),
      li: wrap('li', 'li'),
      td: wrap('td', 'td'),
      th: wrap('th', 'th'),
      strong: wrap('strong', 'strong'),
      em: wrap('em', 'em'),
      blockquote: wrap('blockquote', 'bq'),
      h1: wrap('h1', 'h1'),
      h2: wrap('h2', 'h2'),
      h3: wrap('h3', 'h3'),
      h4: wrap('h4', 'h4'),
      h5: wrap('h5', 'h5'),
      h6: wrap('h6', 'h6'),
    }
  }, [citations])

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none
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
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
