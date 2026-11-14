import { type ReactNode } from 'react'

type SideBar = {
  children: ReactNode
}

function SideBar({ children }: SideBar) {
  return <section>{children}</section>
}

export default SideBar
