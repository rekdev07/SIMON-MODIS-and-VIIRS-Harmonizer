import { useState } from 'react'
import SideBar from '../components/ScreenViewer/SideBar'
import TextField from '../components/fields/TextField'
import DatePicker from '../components/fields/DatePicker'
import Button from '../components/landing/Buttons'

function MapViewer() {
  const [nombre, setNombre] = useState('')
  const [fecha, setFecha] = useState('')

  return (
    <div className="min-h-screen grid grid-cols-[300px_1fr] bg-gray-300">
      <SideBar>
        <h1 className="mb-6 text-xl font-bold">SIMON</h1>
        <p>Step 1. Choose a place</p>
        <div className="flex flex-col gap-5">
          <TextField
            label="Coordinates"
            name="nombre"
            value={nombre}
            onChange={setNombre}
            placeholder="E.g. Latitude, Longitude"
            required
          />

          <p>Step 2. Draw the desired area</p>

          <p>Step 3. Enter the date range to display</p>
          <DatePicker
            label="Start"
            name="fecha"
            value={fecha}
            onChange={setFecha}
            required
          />
          <DatePicker
            label=""
            name="End"
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
