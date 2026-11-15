import { type ReactNode } from 'react'

/** Props of {@link SideBar}. */
type SideBarProps = {
  children: ReactNode
}

/** Left column of the map viewer; scrolls on its own so the map stays full height. */
function SideBar({ children }: SideBarProps) {
  return (
    <section className="h-screen overflow-y-auto bg-gray-50 p-6">
      {children}
    </section>
  )
}

export default SideBar
