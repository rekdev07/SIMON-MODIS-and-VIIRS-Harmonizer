import { type ReactNode } from 'react'


type SelectProps = {
    children: ReactNode
}

function Select({ children }: SelectProps) {
    return (
        <select className='border-mist-800'>{children}</select>
    )
}

export default Select