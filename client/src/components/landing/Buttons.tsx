import { type ReactNode } from 'react'

type ButtonProps = {
    children: ReactNode

}

function Button({ children }: ButtonProps) {
    return <button className='text-cyan-50 bg-blue-400 py-2 px-4 rounded hover:bg-cyan-400'>{children}</button>
}

export default Button;