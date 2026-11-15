import { type ReactNode } from 'react'

/** Props of {@link FloatingBar}. */
type FloatingBarProps = {
  children: ReactNode
  /** Position classes from the caller, e.g. `top-3 right-3 z-[1000]` over a map. */
  className?: string
}

/** Vertical toolbar that floats over the map and holds `FloatingButton`s. */
function FloatingBar({ children, className = '' }: FloatingBarProps) {
  return (
    <div
      className={`absolute flex flex-col gap-0.5 rounded-xl bg-gray-100 p-1.5 shadow ${className}`}
    >
      {children}
    </div>
  )
}

export default FloatingBar
