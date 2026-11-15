import { type PropsWithChildren } from 'react'

function FloatingButton({ children }: PropsWithChildren) {
  return <button className="h-9 w-9 rounded-2xl bg-gray-50">{children}</button>
}

export default FloatingButton
