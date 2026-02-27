import { Search } from 'lucide-react'

export default function DocumentSearch({ value, onChange, placeholder = 'Search documents...' }) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-surface-border bg-white py-2.5 pl-10 pr-4 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
      />
    </div>
  )
}
