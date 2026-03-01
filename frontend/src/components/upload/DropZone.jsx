import { useState, useRef, useCallback } from 'react'
import { Upload } from 'lucide-react'

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

export default function DropZone({ onFiles, accept, className = '' }) {
  const [dragOver, setDragOver] = useState(false)
  const [sizeError, setSizeError] = useState(null)
  const inputRef = useRef(null)

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

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
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
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept || '.pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.webp'}
          onChange={handleChange}
          className="hidden"
        />
      </div>
      {sizeError && (
        <p className="mt-2 text-sm text-red-600">{sizeError}</p>
      )}
    </div>
  )
}
