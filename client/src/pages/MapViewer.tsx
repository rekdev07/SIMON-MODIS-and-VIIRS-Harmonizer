import { useState } from 'react'
import SideBar from '../components/ScreenViewer/SideBar'
import TextField from '../components/fields/TextField'
import DatePicker from '../components/fields/DatePicker'
import Button from '../components/landing/Buttons'
import Select from '../components/landing/Select'

function MapViewer() {
  const [nombre, setNombre] = useState('')
  const [fecha, setFecha] = useState('')

  return (
    <div className="min-h-screen grid grid-cols-[300px_1fr] bg-gray-300">
      <SideBar>
        <h1 className="mb-6 text-xl font-bold">SIMON</h1>
        <p>Paso 1. Elige un lugar</p>
        <div className="flex flex-col gap-5">
          <TextField
            label="Coordenadas"
            name="nombre"
            value={nombre}
            onChange={setNombre}
            placeholder="Ej. Latidudad, Longitud"
            required
          />

          <p>Paso 2. Dibuja el área deseada</p>

          <p>Paso 3. Ingresar el rango de fechas a mostrar</p>
          <DatePicker
            label="Inicio"
            name="fecha"
            value={fecha}
            onChange={setFecha}
            required
          />
          <DatePicker
            label="Fin"
            name="fecha"
            value={fecha}
            onChange={setFecha}
            required
          />
          <Button>Save</Button>

        </div>
      </SideBar>
    </div>
  )
}

export default MapViewer
