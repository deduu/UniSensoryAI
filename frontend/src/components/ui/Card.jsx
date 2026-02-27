export default function Card({ children, className = '', hover = false, ...props }) {
  return (
    <div
      className={`rounded-xl border border-surface-border bg-white shadow-card ${
        hover ? 'transition-shadow hover:shadow-card-hover' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`border-b border-surface-border px-6 py-4 ${className}`}>{children}</div>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={`px-6 py-4 ${className}`}>{children}</div>
}
