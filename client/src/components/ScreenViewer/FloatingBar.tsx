import { type PropsWithChildren } from 'react'

function FloatingBar({ children }: PropsWithChildren) {
  return (
    <div className="absolute flex flex-col gap-0.5 rounded-xl bg-gray-100 p-1.5">
      {children}
    </div>
  )
}

export default FloatingBar
