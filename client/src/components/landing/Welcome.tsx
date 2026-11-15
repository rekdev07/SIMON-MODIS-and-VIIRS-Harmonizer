
import { Link } from "react-router-dom";

function Welcome() {
  return (
    <section
      id="inicio"
      className="flex min-h-[550px] flex-col items-center justify-center bg-emerald-50 px-6 text-center"
    >
      <span className="mb-4 rounded-full bg-emerald-100 px-4 py-2 text-sm font-medium text-emerald-700">
        Explora nuevos lugares
      </span>

      <h1 className="mb-6 max-w-3xl text-5xl font-bold text-gray-900">
        Descubre el mundo desde una nueva perspectiva
      </h1>

      <p className="mb-8 max-w-xl text-lg text-gray-600">
        Explora ubicaciones, descubre nuevos lugares y
        encuentra tu próximo destino con nuestra plataforma.
      </p>

      <Link
        to="/mapa"
        className="rounded-lg bg-emerald-700 px-8 py-3 font-semibold text-white transition hover:bg-emerald-800"
      >
        Comenzar a explorar
      </Link>
    </section>
  );
}

export default Welcome;
