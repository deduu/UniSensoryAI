import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'unisensory:inspector:v3'
const MIN_WIDTH = 320
const DEFAULT_WIDTH = 550

function loadPersistedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return null
}

function persistState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* ignore */
  }
}

/**
 * Hook for a resizable inspector pane docked to the right.
 *
 * @returns Pane state and control functions
 */
export function useResizablePane() {
  const persisted = loadPersistedState()

  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)
  
  const dockPosition = 'right' // Forced to right only
  const [paneWidth, setPaneWidth] = useState(persisted?.width || DEFAULT_WIDTH)
  const [isDragging, setIsDragging] = useState(false)

  // Persist width on changes
  useEffect(() => {
    persistState({ width: paneWidth })
  }, [paneWidth])

  const open = useCallback(() => {
    setIsOpen(true)
    setIsMinimized(false)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
    setIsMinimized(false)
    setIsMaximized(false)
  }, [])

  const minimize = useCallback(() => {
    setIsMinimized(true)
    setIsMaximized(false)
  }, [])

  const maximize = useCallback(() => {
    setIsMaximized(true)
    setIsMinimized(false)
  }, [])

  const restore = useCallback(() => {
    setIsMinimized(false)
    setIsMaximized(false)
  }, [])

  // Drag resize handler
  const onDragStart = useCallback(
    (e) => {
      e.preventDefault()
      setIsDragging(true)

      const startX = e.clientX
      const startWidth = paneWidth

      // Add the resizing class to prevent text selection
      document.body.classList.add('is-resizing')

      const onMouseMove = (moveEvent) => {
        const delta = startX - moveEvent.clientX
        const maxWidth = Math.floor(window.innerWidth * 0.8) // Allow up to 80%
        const newWidth = Math.max(MIN_WIDTH, Math.min(maxWidth, startWidth + delta))
        setPaneWidth(newWidth)
      }

      const onMouseUp = () => {
        setIsDragging(false)
        document.body.classList.remove('is-resizing')
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
      }

      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    },
    [paneWidth]
  )

  return {
    isOpen,
    isMinimized,
    isMaximized,
    isDragging,
    dockPosition,
    paneWidth,
    open,
    close,
    minimize,
    maximize,
    restore,
    onDragStart,
  }
}
