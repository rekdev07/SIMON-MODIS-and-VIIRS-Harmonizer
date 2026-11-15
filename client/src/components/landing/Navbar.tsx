
function Navbar() {
  return (
    <nav className="flex items-center justify-between px-8 py-5 bg-white shadow-sm">
      <a href="#inicio" className="text-2xl font-bold text-emerald-700">
        GeoExplora
      </a>

      <div className="flex items-center gap-8">
        <a href="#inicio" className="text-gray-600 hover:text-emerald-700">
          Inicio
        </a>

        <a href="#descripcion" className="text-gray-600 hover:text-emerald-700">
          Nosotros
        </a>

        <a href="#footer" className="text-gray-600 hover:text-emerald-700">
          Contacto
        </a>
      </div>
    </nav>
  );
}

export default Navbar;
