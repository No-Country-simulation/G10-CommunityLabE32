'use client';

import { useEffect, useMemo, useState } from 'react';
import { obtenerMensajes, Mensaje } from '@/services/api';
import { Search, ChevronLeft, ChevronRight, Filter, Loader2, X } from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';

type FiltroSentimiento = 'todos' | 'positivo' | 'negativo' | 'sin';

const filtros: { valor: FiltroSentimiento; etiqueta: string }[] = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'positivo', etiqueta: 'Positivo' },
  { valor: 'negativo', etiqueta: 'Negativo' },
  { valor: 'sin', etiqueta: 'Sin clasificar' },
];

const sentimentBadge: Record<string, string> = {
  positivo: 'badge-success',
  negativo: 'badge-danger',
};

export default function InteraccionesPage() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [totalRegistros, setTotalRegistros] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState('');
  const [filtroSentimiento, setFiltroSentimiento] = useState<FiltroSentimiento>('todos');
  const [mostrarFiltros, setMostrarFiltros] = useState(false);

  const [paginaActual, setPaginaActual] = useState(1);
  const itemsPorPagina = 10;

  useEffect(() => {
    let vigente = true;
    obtenerMensajes((paginaActual - 1) * itemsPorPagina, itemsPorPagina)
      .then((data) => {
        if (!vigente) return;
        setMensajes(data.items);
        setTotalRegistros(data.total);
        setCargando(false);
      })
      .catch((error) => {
        if (vigente) setCargando(false);
        console.error('Error conectando al backend:', error);
      });
    return () => {
      vigente = false;
    };
  }, [paginaActual]);

  const totalPaginas = Math.ceil(totalRegistros / itemsPorPagina);
  const indicePrimerItem = (paginaActual - 1) * itemsPorPagina;
  const indiceUltimoItem = Math.min(indicePrimerItem + itemsPorPagina, totalRegistros);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return mensajes.filter((m) => {
      const s = m.sentimiento_ref ?? '';
      const okSentimiento =
        filtroSentimiento === 'todos' ||
        (filtroSentimiento === 'sin' ? !s : s === filtroSentimiento);
      const okBusqueda =
        !q || [m.autor, m.texto, m.canal].some((v) => v?.toLowerCase().includes(q));
      return okSentimiento && okBusqueda;
    });
  }, [mensajes, busqueda, filtroSentimiento]);

  const positivos = mensajes.filter((m) => m.sentimiento_ref === 'positivo').length;
  const negativos = mensajes.filter((m) => m.sentimiento_ref === 'negativo').length;
  const sinClasificar = mensajes.filter((m) => !m.sentimiento_ref).length;

  const stats = [
    { etiqueta: 'Total registros', valor: totalRegistros, color: 'text-foreground' },
    { etiqueta: 'Positivos (página)', valor: positivos, color: 'text-success' },
    { etiqueta: 'Negativos (página)', valor: negativos, color: 'text-danger' },
    { etiqueta: 'Sin clasificar (página)', valor: sinClasificar, color: 'text-muted-foreground' },
  ];

  const hayFiltroActivo = busqueda.trim() !== '' || filtroSentimiento !== 'todos';

  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="flex-1 min-w-0 p-6 md:p-10 flex flex-col h-screen overflow-hidden">
        <header className="mb-6 shrink-0">
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Interacciones ingeridas
          </h1>
          <p className="text-muted-foreground mt-1.5 text-[15px]">
            Explora la base de conocimiento comunitaria completa.
          </p>
        </header>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 shrink-0">
          {stats.map((s) => (
            <div key={s.etiqueta} className="card px-5 py-4">
              <p className="text-xs font-medium uppercase tracking-wider text-subtle-foreground">
                {s.etiqueta}
              </p>
              <p className={`mt-1 text-2xl font-bold tabular-nums ${s.color}`}>{s.valor}</p>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 mb-3 shrink-0">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle-foreground" />
            <input
              type="text"
              placeholder="Buscar autor, mensaje o canal…"
              className="input pl-10"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
          </div>
          <button
            onClick={() => setMostrarFiltros((v) => !v)}
            className="btn-secondary ml-auto"
            aria-expanded={mostrarFiltros}
          >
            <Filter className="w-4 h-4" /> Filtros
            {filtroSentimiento !== 'todos' && (
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            )}
          </button>
        </div>

        {mostrarFiltros && (
          <div className="card px-4 py-3 mb-3 flex flex-wrap items-center gap-2 shrink-0">
            <span className="text-xs font-semibold uppercase tracking-wider text-subtle-foreground mr-2">
              Sentimiento
            </span>
            {filtros.map((f) => (
              <button
                key={f.valor}
                onClick={() => setFiltroSentimiento(f.valor)}
                className={filtroSentimiento === f.valor ? 'badge-primary' : 'badge-neutral'}
              >
                {f.etiqueta}
              </button>
            ))}
            {hayFiltroActivo && (
              <button
                onClick={() => {
                  setBusqueda('');
                  setFiltroSentimiento('todos');
                }}
                className="btn-ghost ml-auto !py-1.5"
              >
                <X className="w-3.5 h-3.5" /> Limpiar
              </button>
            )}
          </div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="card mt-2 flex-1 min-h-0 overflow-hidden flex flex-col"
        >
          <div className="overflow-auto flex-1">
            <table className="min-w-full">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr>
                  <th scope="col" className="table-th">Autor</th>
                  <th scope="col" className="table-th">Mensaje</th>
                  <th scope="col" className="table-th">Canal</th>
                  <th scope="col" className="table-th">Sentimiento</th>
                </tr>
              </thead>
              <tbody>
                {cargando ? (
                  <tr>
                    <td colSpan={4} className="table-td py-14 text-center text-subtle-foreground">
                      <span className="inline-flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-primary" /> Cargando base de datos…
                      </span>
                    </td>
                  </tr>
                ) : filtrados.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="table-td py-14 text-center text-subtle-foreground">
                      {mensajes.length === 0 ? 'No hay mensajes.' : 'Ningún resultado con estos filtros.'}
                    </td>
                  </tr>
                ) : (
                  filtrados.map((msg) => (
                    <tr key={msg.id_mensaje} className="table-row">
                      <td className="table-td whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center text-white text-[11px] font-bold shrink-0">
                            {msg.autor.substring(0, 2).toUpperCase()}
                          </div>
                          <span className="font-medium text-foreground">{msg.autor}</span>
                        </div>
                      </td>
                      <td className="table-td">
                        <div className="text-muted-foreground line-clamp-2 max-w-xl" title={msg.texto}>
                          {msg.texto}
                        </div>
                      </td>
                      <td className="table-td whitespace-nowrap">
                        <span className="badge-neutral">{msg.canal}</span>
                      </td>
                      <td className="table-td whitespace-nowrap">
                        <span className={sentimentBadge[msg.sentimiento_ref ?? ''] ?? 'badge-neutral'}>
                          {msg.sentimiento_ref || 'N/A'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-5 py-3.5 border-t border-border flex items-center justify-between shrink-0 bg-surface">
            <div className="text-sm text-subtle-foreground">
              Mostrando{' '}
              <span className="text-foreground font-medium">
                {totalRegistros > 0 ? indicePrimerItem + 1 : 0}
              </span>{' '}
              a <span className="text-foreground font-medium">{indiceUltimoItem}</span> de{' '}
              <span className="text-foreground font-medium">{totalRegistros}</span> resultados
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPaginaActual((p) => Math.max(1, p - 1))}
                disabled={paginaActual === 1}
                className="btn-secondary px-2.5! py-2!"
                aria-label="Página anterior"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-subtle-foreground tabular-nums">
                Pág {paginaActual} / {totalPaginas || 1}
              </span>
              <button
                onClick={() => setPaginaActual((p) => Math.min(totalPaginas, p + 1))}
                disabled={paginaActual === totalPaginas || totalPaginas === 0}
                className="btn-secondary px-2.5! py-2!"
                aria-label="Página siguiente"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}