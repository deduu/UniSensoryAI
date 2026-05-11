import { useState, useRef, useCallback, useImperativeHandle, forwardRef } from 'react'
import { Upload, Paperclip } from 'lucide-react'

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB

function validateFiles(fileList) {
  const valid = []
  const rejected = []
  for (const file of Array.from(fileList)) {
    if (file.size > MAX_FILE_SIZE) {
      rejected.push(file.name)
    } else {
      valid.push(file)
    }
  }
  return { valid, rejected }
}

const DropZone = forwardRef(function DropZone(
  { onFiles, accept, size = 'full', className = '' },
  ref
) {
  const [dragOver, setDragOver] = useState(false)
  const [sizeError, setSizeError] = useState(null)
  const inputRef = useRef(null)

  useImperativeHandle(ref, () => ({
    openFilePicker: () => inputRef.current?.click(),
  }), [])

  const processFiles = useCallback(
    (fileList) => {
      const { valid, rejected } = validateFiles(fileList)
      if (rejected.length > 0) {
        setSizeError(`Too large (>50 MB): ${rejected.join(', ')}`)
      } else {
        setSizeError(null)
      }
      if (valid.length > 0) onFiles(valid)
    },
    [onFiles]
  )

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragOver(false)
      const files = e.dataTransfer?.files
      if (files?.length) processFiles(files)
    },
    [processFiles]
  )

  const handleChange = useCallback(
    (e) => {
      const files = e.target.files
      if (files?.length) processFiles(files)
      e.target.value = ''
    },
    [processFiles]
  )

  const sharedInput = (
    <input
      ref={inputRef}
      type="file"
      multiple
      accept={accept || '.pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.webp'}
      onChange={handleChange}
      className="hidden"
    />
  )

  const dragHandlers = {
    onDragOver: (e) => { e.preventDefault(); setDragOver(true) },
    onDragLeave: () => setDragOver(false),
    onDrop: handleDrop,
    onClick: () => inputRef.current?.click(),
  }

  if (size === 'compact') {
    return (
      <div
        {...dragHandlers}
        className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed px-3 py-1.5 text-xs transition-colors ${
          dragOver
            ? 'border-brand bg-brand/5 text-brand'
            : 'border-surface-border text-ink-muted hover:border-brand/50 hover:text-ink'
        } ${className}`}
      >
        <Paperclip className="h-3.5 w-3.5 shrink-0" />
        <span>Drop or browse</span>
        {sharedInput}
      </div>
    )
  }

  if (size === 'medium') {
    return (
      <div
        {...dragHandlers}
        className={`flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed px-4 py-3 transition-colors ${
          dragOver
            ? 'border-brand bg-brand-light/30'
            : 'border-brand/30 bg-brand/5 hover:border-brand/50 hover:bg-brand/10'
        } ${className}`}
      >
        <Upload className={`h-5 w-5 shrink-0 ${dragOver ? 'text-brand' : 'text-brand/70'}`} />
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="text-sm font-medium text-ink whitespace-nowrap">
            Drop files here or <span className="text-brand">browse</span>
          </span>
          <span className="hidden md:inline text-xs text-ink-faint truncate">
            · PDF, DOCX, XLSX, PPTX, PNG, JPG · 50 MB max
          </span>
        </div>
        {sharedInput}
        {sizeError && (
          <span className="ml-auto text-xs text-red-500 truncate" title={sizeError}>
            {sizeError}
          </span>
        )}
      </div>
    )
  }

  return (
    <div>
      <div
        {...dragHandlers}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
          dragOver
            ? 'border-brand bg-brand-light/30'
            : 'border-surface-border hover:border-brand/50 hover:bg-surface-subtle'
        } ${className}`}
      >
        <Upload className={`mb-3 h-10 w-10 ${dragOver ? 'text-brand' : 'text-ink-faint'}`} />
        <p className="text-sm font-medium text-ink">
          Drop files here or <span className="text-brand">browse</span>
        </p>
        <p className="mt-1 text-xs text-ink-muted">
          PDF, DOCX, XLSX, PPTX, PNG, JPG up to 50 MB
        </p>
        {sharedInput}
      </div>
      {sizeError && (
        <p className="mt-2 text-sm text-red-600">{sizeError}</p>
      )}
    </div>
  )
})

export default DropZone
