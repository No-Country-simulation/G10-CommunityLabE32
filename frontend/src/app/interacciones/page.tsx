'use client';


import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import {
  obtenerMensajes, obtenerResumenSentimiento, FiltroSentimiento as FiltroApi, Mensaje, ResumenSentimiento,
} from '@/services/api';
import { Search, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import RutaProtegida from '@/components/RutaProtegida';

type FiltroSentimiento = 'todos' | FiltroApi;

function etiquetaTipo(tipo: string | null | undefined): string {
  const clave = (tipo ?? '').trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[\s-]+/g, '_');
  const etiquetas: Record<string, string> = {
    PREGUNTA_TECNICA: 'Duda', PREGUNTA: 'Duda', DUDA: 'Duda',
    CONSULTA_NEGOCIO: 'Consulta', CONSULTA: 'Consulta',
    LOGRO: 'Logro', EXITO: 'Éxito', CASO_DE_EXITO: 'Éxito', TESTIMONIO: 'Testimonio',
    BLOQUEO: 'Bloqueo', PROBLEMA: 'Problema',
    COMENTARIO: 'Comentario', SUGERENCIA: 'Sugerencia',
    SIN_CLASIFICAR: 'Sin clasificar',
  };
  return clave ? etiquetas[clave] ?? 'Otro' : 'Sin clasificar';
}


const sentimentBadge: Record<string, string> = {
  positivo: 'sentiment-label sentiment-positive',
  negativo: 'sentiment-label sentiment-negative',
  neutral: 'sentiment-label sentiment-neutral',
  indeterminado: 'sentiment-label sentiment-unknown',
};
const ETIQUETA_SENTIMIENTO: Record<string, string> = {
  positivo: 'Positivo', negativo: 'Negativo', neutral: 'Neutral', indeterminado: 'Indeterminado',
};


export default function InteraccionesPage() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [totalRegistros, setTotalRegistros] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState('');
  const [filtroSentimiento, setFiltroSentimiento] = useState<FiltroSentimiento>('todos');
  const [buscadorAbierto, setBuscadorAbierto] = useState(false);
  const [busquedaAplicada, setBusquedaAplicada] = useState('');
  const [errorCarga, setErrorCarga] = useState('');
  const [resumen, setResumen] = useState<ResumenSentimiento | null>(null);

  const [paginaActual, setPaginaActual] = useState(1);
  const itemsPorPagina = 10;

  useEffect(() => {
    const cerrarBuscador = () => { setBuscadorAbierto(false); setBusqueda(''); setBusquedaAplicada(''); setPaginaActual(1); };
    const timer = setTimeout(cerrarBuscador, 0);
    window.addEventListener('pageshow', cerrarBuscador);
    return () => { clearTimeout(timer); window.removeEventListener('pageshow', cerrarBuscador); };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { setBusquedaAplicada(busqueda.trim()); setPaginaActual(1); }, 350);
    return () => clearTimeout(timer);
  }, [busqueda]);

  useEffect(() => {
    let vigente = true;
    let consultando = false;
    const cargar = async (inicial = false) => {
      if (consultando) return;
      consultando = true;
      if (inicial) setCargando(true);
      setErrorCarga('');
      try {
        const data = await obtenerMensajes((paginaActual - 1) * itemsPorPagina, itemsPorPagina, undefined, null,
          filtroSentimiento === 'todos' ? undefined : filtroSentimiento, busquedaAplicada);
        if (!vigente) return;
        setMensajes(data.items); setTotalRegistros(data.total);
      } catch { if (vigente) { if (inicial) { setMensajes([]); setTotalRegistros(0); } setErrorCarga('No se pudieron actualizar los mensajes. Inténtalo de nuevo.'); } }
      finally { consultando = false; if (vigente) setCargando(false); }
    };
    cargar(true);
    const timer = setInterval(() => { if (document.visibilityState === 'visible') cargar(); }, 15000);
    return () => { vigente = false; clearInterval(timer); };
  }, [paginaActual, filtroSentimiento, busquedaAplicada]);

  useEffect(() => {
    let vigente = true;
    const cargar = () => obtenerResumenSentimiento()
      .then((data) => { if (vigente) setResumen(data); })
      .catch((error) => console.error('Error al cargar el resumen de sentimiento:', error));
    cargar();
    const timer = setInterval(() => { if (document.visibilityState === 'visible') cargar(); }, 15000);
    return () => { vigente = false; clearInterval(timer); };
  }, []);

  const elegirFiltro = (valor: FiltroSentimiento) => {
    if (valor === filtroSentimiento) return;
    setFiltroSentimiento(valor);
    setPaginaActual(1);
    setCargando(true);
  };

  const totalPaginas = Math.ceil(totalRegistros / itemsPorPagina);
  const indicePrimerItem = (paginaActual - 1) * itemsPorPagina;
  const indiceUltimoItem = Math.min(indicePrimerItem + itemsPorPagina, totalRegistros);

  const filtrados = mensajes;

  const stats = [
    { filtro: 'todos' as FiltroSentimiento, etiqueta: 'Total de mensajes', valor: resumen?.total ?? '—' },
    { filtro: 'positivo' as FiltroSentimiento, etiqueta: 'Positivos', valor: resumen?.por_valor.positivo ?? '—' },
    { filtro: 'negativo' as FiltroSentimiento, etiqueta: 'Negativos', valor: resumen?.por_valor.negativo ?? '—' },
    { filtro: 'neutral' as FiltroSentimiento, etiqueta: 'Neutrales', valor: resumen?.por_valor.neutral ?? '—' },
    { filtro: 'indeterminado' as FiltroSentimiento, etiqueta: 'Indeterminados', valor: resumen?.por_valor.indeterminado ?? '—' },
    { filtro: 'sin_analizar' as FiltroSentimiento, etiqueta: 'Sin analizar', valor: resumen?.sin_analizar ?? '—' },
  ];

  const tituloListado = stats.find(item => item.filtro === filtroSentimiento)?.etiqueta ?? 'Total de mensajes';

  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="interactions-page dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 flex flex-col min-h-[calc(100dvh-var(--topbar-h))] md:h-[calc(100dvh-var(--topbar-h))] md:overflow-hidden">
          <header className="mb-6 shrink-0">
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
              Interacciones importadas
            </h1>
            <p className="text-muted-foreground mt-1.5 text-[15px]">
              Explora la base de conocimiento comunitaria completa.
            </p>
          </header>

          <div className="interaction-stats grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 mb-6 shrink-0" role="group" aria-label="Filtrar por sentimiento">
            {stats.map((s) => (
              <button type="button" key={s.etiqueta} data-filtro={s.filtro} className="interaction-stat card px-5 py-4 text-left" aria-pressed={filtroSentimiento === s.filtro} onClick={() => elegirFiltro(s.filtro)}>
                <p className="text-xs font-medium uppercase tracking-wider text-subtle-foreground">
                  {s.etiqueta}
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums">{s.valor}</p>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 mb-3 shrink-0">
            <div className="interaction-keyword-search" role="search">
              <button type="button" className="interaction-search-toggle" aria-label={buscadorAbierto ? 'Cerrar búsqueda' : 'Buscar por palabra clave'} aria-expanded={buscadorAbierto} aria-controls="busqueda-interacciones" onClick={() => { setBuscadorAbierto(v => !v); if (buscadorAbierto) setBusqueda(''); }}><Search className="w-4 h-4" aria-hidden="true" /></button>
              {buscadorAbierto && <input id="busqueda-interacciones" className="input interaction-keyword-input" type="search" aria-label="Buscar por palabra clave" autoFocus value={busqueda} onChange={e => setBusqueda(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') { setBuscadorAbierto(false); setBusqueda(''); } }} />}
            </div>
            {filtroSentimiento !== 'todos' && <h2 className="text-base font-bold">{tituloListado}</h2>}
          </div>
          {busquedaAplicada && <p className="text-sm text-muted-foreground mb-3">Resultados para «<span translate="no">{busquedaAplicada}</span>»</p>}
          {errorCarga && <p role="alert" className="text-sm text-danger mb-3">{errorCarga}</p>}

          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="interaction-table-card card mt-2 flex-none md:flex-1 min-h-0 overflow-hidden flex flex-col"
          >
            <div className="interaction-table-scroll overflow-x-auto md:overflow-auto md:flex-1">
              <table className="interaction-table min-w-full">
                <thead className="sticky top-0 z-10 bg-surface">
                  <tr>
                    <th scope="col" className="table-th">Autor</th>
                    <th scope="col" className="table-th">Mensaje</th>
                    <th scope="col" className="table-th">Tipo</th>
                    <th scope="col" className="table-th">Sentimiento detectado</th>
                  </tr>
                </thead>
                <tbody>
                  {cargando ? (
                    <tr>
                      <td colSpan={4} className="table-td py-14 text-center text-subtle-foreground">
                        <span className="inline-flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-primary" /> Cargando mensajes…
                        </span>
                      </td>
                    </tr>
                  ) : filtrados.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="table-td py-14 text-center text-subtle-foreground">
                        {errorCarga ? 'Los mensajes no están disponibles.' : busquedaAplicada || filtroSentimiento !== 'todos' ? 'No hay resultados con estos filtros.' : 'No hay mensajes.'}
                      </td>
                    </tr>
                  ) : (
                    filtrados.map((msg) => (
                      <tr key={msg.id_mensaje} className="table-row">
                        <td data-label="Autor" className="table-td whitespace-nowrap">
                          <div className="flex items-center gap-3">
                            <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center text-white text-[11px] font-bold shrink-0" translate="no">
                              {/^\d{16,22}$/.test(msg.autor) ? 'CL' : msg.autor.substring(0, 2).toUpperCase()}
                            </div>
                            <span className="font-medium text-foreground" translate="no">{/^\d{16,22}$/.test(msg.autor) ? 'Integrante de Discord' : msg.autor}</span>
                          </div>
                        </td>
                        <td data-label="Mensaje" className="table-td">
                          <div className="text-muted-foreground md:line-clamp-2 max-w-xl" title={msg.texto} translate="no">
                            {msg.texto}
                          </div>
                        </td>
                        <td data-label="Tipo" className="table-td whitespace-nowrap">
                          <span className="badge-neutral" title={msg.tipo || 'Sin clasificación disponible'}>{etiquetaTipo(msg.tipo)}</span>
                          {msg.tema_ref && <div className="mt-1 text-xs text-muted-foreground max-w-[12rem] truncate" title={msg.tema_ref} translate="no">{msg.tema_ref}</div>}
                        </td>
                        <td data-label="Sentimiento detectado" className="table-td whitespace-nowrap">
                          <span
                            className={msg.sentimiento_ref ? sentimentBadge[msg.sentimiento_ref] ?? 'badge-neutral' : 'sentiment-label sentiment-pending'}
                            title={msg.sentimiento_version ? `Análisis ${msg.sentimiento_origen ?? ''} · ${msg.sentimiento_version}` : undefined}
                          >
                            {ETIQUETA_SENTIMIENTO[msg.sentimiento_ref ?? ''] ?? 'Sin analizar'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="px-4 py-3.5 border-t border-border flex flex-wrap gap-3 items-center justify-between shrink-0 bg-surface">
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
                  Página {paginaActual} de {totalPaginas || 1}
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
    </RutaProtegida>
  )}</UiTree>;
}