import Badge from '../ui/Badge'

const LABEL_MAP = {
  queued: 'Queued',
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

export default function JobStatusBadge({ status }) {
  const normalized = status?.toLowerCase() || 'pending'
  return (
    <Badge variant={normalized} dot>
      {LABEL_MAP[normalized] || status}
    </Badge>
  )
}
