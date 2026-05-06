import { useState } from 'react'
import { Plus, MessageSquare, Search, Trash2, MoreHorizontal, PanelLeftClose, PanelLeft } from 'lucide-react'

export default function ChatSidebar({ conversations, activeId, onSelect, onNew, onDelete, collapsed, onToggle }) {
  const [search, setSearch] = useState('')
  const [menuOpenId, setMenuOpenId] = useState(null)

  const filtered = search.trim()
    ? conversations.filter((c) => c.title.toLowerCase().includes(search.toLowerCase()))
    : conversations

  const formatTime = (isoStr) => {
    if (!isoStr) return ''
    const d = new Date(isoStr)
    const diff = Date.now() - d
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return d.toLocaleDateString()
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-3 gap-2 border-r border-surface-border/50 bg-surface/20 backdrop-blur-sm w-12 shrink-0">
        <button onClick={onToggle} className="p-2 rounded-lg text-ink-muted hover:bg-surface-subtle hover:text-ink transition-colors" title="Expand sidebar">
          <PanelLeft className="h-4 w-4" />
        </button>
        <button onClick={onNew} className="p-2 rounded-lg bg-brand/15 text-brand-hover hover:bg-brand/25 transition-colors" title="New chat">
          <Plus className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-72 shrink-0 border-r border-surface-border/50 bg-surface/20 backdrop-blur-sm">
      <div className="flex items-center justify-between px-3 py-3 border-b border-surface-border/50">
        <button onClick={onNew} className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-brand/15 px-3 py-2 text-xs font-medium text-brand-hover border border-brand/20 hover:bg-brand/25 hover:border-brand/40 transition-all duration-200">
          <Plus className="h-3.5 w-3.5" /> New Chat
        </button>
        <button onClick={onToggle} className="ml-2 p-2 rounded-lg text-ink-muted hover:bg-surface-subtle hover:text-ink transition-colors" title="Collapse sidebar">
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>
      <div className="px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-faint" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search conversations..." className="w-full rounded-lg bg-surface-muted/50 border border-surface-border pl-8 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-brand/30 focus:outline-none focus:ring-1 focus:ring-brand/20 transition-all" />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <MessageSquare className="h-8 w-8 text-ink-faint mb-2" />
            <p className="text-xs text-ink-faint">{search ? 'No matching conversations' : 'No conversations yet'}</p>
          </div>
        ) : (
          filtered.map((conv) => (
            <div key={conv.id} className="relative group">
              <button onClick={() => onSelect(conv.id)} className={`w-full text-left rounded-xl px-3 py-2.5 transition-all duration-150 ${conv.id === activeId ? 'bg-brand/15 border border-brand/25' : 'hover:bg-surface-subtle border border-transparent'}`}>
                <p className={`text-xs font-medium truncate ${conv.id === activeId ? 'text-ink' : 'text-ink-muted'}`}>{conv.title}</p>
                <p className="text-[10px] text-ink-faint mt-0.5">{formatTime(conv.updated_at || conv.created_at)}</p>
              </button>
              <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === conv.id ? null : conv.id) }} className="p-1.5 rounded-lg text-ink-faint hover:bg-surface-muted hover:text-ink transition-colors">
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </button>
                {menuOpenId === conv.id && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setMenuOpenId(null)} />
                    <div className="absolute right-0 top-full mt-1 z-50 w-36 rounded-xl border border-surface-border bg-surface-muted/95 backdrop-blur-xl shadow-modal animate-fade-in overflow-hidden">
                      <button onClick={(e) => { e.stopPropagation(); onDelete(conv.id); setMenuOpenId(null) }} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors">
                        <Trash2 className="h-3.5 w-3.5" /> Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
