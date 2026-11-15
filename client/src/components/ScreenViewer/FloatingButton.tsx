import { type ReactNode } from 'react'

/** Props of {@link FloatingButton}. */
type FloatingButtonProps = {
  children: ReactNode
  /** Tooltip and accessible name (the button usually only shows an icon). */
  title: string
  onClick?: () => void
  /** Highlights the button with the blue accent, e.g. while a tool is on. */
  active?: boolean
  disabled?: boolean
}

/** Square icon button for the map's `FloatingBar`. */
function FloatingButton({
  children,
  title,
  onClick,
  active = false,
  disabled = false,
}: FloatingButtonProps) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={active}
      onClick={onClick}
      disabled={disabled}
      className={`flex h-9 w-9 items-center justify-center rounded-sm transition disabled:cursor-not-allowed disabled:opacity-40 ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-gray-50 text-gray-700 enabled:hover:bg-gray-200'
      }`}
    >
      {children}
    </button>
  )
}

export default FloatingButton
