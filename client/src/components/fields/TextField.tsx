interface TextFieldProps {
  label: string
  name: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
  required?: boolean
  disabled?: boolean
}

function TextField({
  label,
  name,
  value,
  placeholder = 'Escribe aquí...',
  onChange,
  required = false,
  disabled = false,
}: TextFieldProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      <label htmlFor={name} className="text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>

      <input
        id={name}
        name={name}
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        disabled={disabled}
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-800 transition outline-none placeholder:text-gray-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-gray-100"
      />
    </div>
  )
}

export default TextField
