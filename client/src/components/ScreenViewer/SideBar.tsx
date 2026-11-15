import { type ReactNode } from 'react'

type SideBar = {
  children: ReactNode
}

function SideBar({ children }: SideBar) {
  return <section className='bg-gray-50 p-6'>{children}</section>
}

export default SideBar
