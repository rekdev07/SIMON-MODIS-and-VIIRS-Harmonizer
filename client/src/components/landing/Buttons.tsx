import { type ReactNode } from 'react'

/** Props of {@link Button}. */
type ButtonProps = {
  children: ReactNode
  onClick?: () => void
  type?: 'button' | 'submit'
  /** Disabled buttons are grayed out and ignore clicks. */
  disabled?: boolean
  /** `primary` = solid blue (main action), `secondary` = outlined. */
  variant?: 'primary' | 'secondary'
}

const VARIANTS = {
  primary:
    'bg-blue-600 text-cyan-50 enabled:hover:bg-blue-500 enabled:active:bg-blue-400',
  secondary:
    'border border-blue-600 bg-white text-blue-600 enabled:hover:bg-blue-50 enabled:active:bg-blue-100',
}

/** Shared button with a visible disabled state. */
function Button({
  children,
  onClick,
  type = 'button',
  disabled = false,
  variant = 'primary',
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded px-4 py-2 transition disabled:cursor-not-allowed disabled:border-gray-300 disabled:bg-gray-300 disabled:text-gray-500 ${VARIANTS[variant]}`}
    >
      {children}
    </button>
  )
}

export default Button
