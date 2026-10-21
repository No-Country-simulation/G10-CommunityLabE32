'use client';


import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import {
  obtenerKPIs,
  obtenerResumenSentimiento,
  obtenerAmbitos,
  Ambito,
  DashboardKPIs,
  ResumenSentimiento,
} from '@/services/api';
import {
  BarChart3,
  PieChart,
  TrendingUp,
  Layers,
  ShieldAlert,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Info,
} from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import SelectorLotes from '@/components/SelectorLotes';
import RutaProtegida from '@/components/RutaProtegida';

export default function AnaliticaPage() {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [resumen, setResumen] = useState<ResumenSentimiento | null>(null);
  const [ambitos, setAmbitos] = useState<Ambito[]>([]);
  const [seleccion, setSeleccion] = useState<Ambito[] | null>(null);
  const [consulta, setConsulta] = useState<{ lotes: Ambito[] | null; version: number }>({ lotes: null, version: 0 });
  const [aplicados, setAplicados] = useState<Ambito[] | null>(null);
  const [errorCarga, setErrorCarga] = useState('');
  const [errorLotes, setErrorLotes] = useState('');
  const [cargando, setCargando] = useState(true);

  // Estado para interactividad de la dona (hover en segmentos o leyendas)
  const [segmentoActivo, setSegmentoActivo] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    obtenerAmbitos().then(datos => { if (vigente) setAmbitos(datos); }).catch(() => { if (vigente) setErrorLotes('No se pudo cargar la lista de lotes.'); });
    return () => { vigente = false; };
  }, []);

  useEffect(() => {
    let montado = true;
    const ejecutarCarga = async () => {
      setCargando(true);
      setErrorCarga('');
      try {
        const [kpiData, resData] = await Promise.all([
          obtenerKPIs(consulta.lotes),
          obtenerResumenSentimiento(undefined, consulta.lotes),
        ]);
        if (!montado) return;
        setKpis(kpiData);
        setResumen(resData);
        setAplicados(consulta.lotes);
      } catch (err) {
        if (!montado) return;
        console.error('Error cargando analítica:', err);
        setErrorCarga('No se pudieron actualizar los lotes seleccionados. Se mantienen los últimos resultados cargados.');
      } finally {
        if (montado) setCargando(false);
      }
    };

    ejecutarCarga();
    return () => {
      montado = false;
    };
  }, [consulta]);

  const cargarDatos = () => {
    if (cargando) return;
    setCargando(true);
    setConsulta((anterior) => ({ lotes: seleccion ? [...seleccion] : null, version: anterior.version + 1 }));
  };

  // Cálculos seguros para la Gráfica de Anillo
  const analizados = resumen?.analizados ?? 0;
  const pos = resumen?.por_valor.positivo ?? 0;
  const neg = resumen?.por_valor.negativo ?? 0;
  const neu = resumen?.por_valor.neutral ?? 0;
  const ind = resumen?.por_valor.indeterminado ?? 0;

  const pctPos = analizados > 0 ? Math.round((pos / analizados) * 100) : 0;
  const pctNeu = analizados > 0 ? Math.round((neu / analizados) * 100) : 0;
  const pctNeg = analizados > 0 ? Math.round((neg / analizados) * 100) : 0;
  const pctInd = analizados > 0 ? Math.round((ind / analizados) * 100) : 0;

  // Embudo de Curaduría
  const estadosActivos = [
    {
      etiqueta: 'Generados',
      cantidad: kpis?.activos_por_estado?.generado ?? 0,
      color: '#f1f333',
    },
    {
      etiqueta: 'Revisados',
      cantidad: kpis?.activos_por_estado?.revisado ?? 0,
      color: '#f1f333',
    },
    {
      etiqueta: 'Aprobados',
      cantidad: kpis?.activos_por_estado?.aprobado ?? 0,
      color: '#b9e9c5',
    },
    {
      etiqueta: 'Denegados',
      cantidad: kpis?.activos_por_estado?.rechazado ?? 0,
      color: '#ff90e8',
    },
  ];
  const totalActivos = Math.max(1, kpis?.activos_generados ?? 1);

  const nombresTipo: Record<string, string> = {
    PREGUNTA_TECNICA: 'Preguntas técnicas',
    CONSULTA_NEGOCIO: 'Consultas de negocio',
    LOGRO: 'Logros compartidos',
    BLOQUEO: 'Situaciones de bloqueo',
    COMENTARIO: 'Comentarios',
    SIN_CLASIFICAR: 'Sin clasificar',
  };
  const coloresTema = ['#ff90e8', '#f1f333', '#90a8ed', '#b9e9c5'];
  const temas = Object.entries(kpis?.mensajes_por_tipo ?? {})
    .filter(([tipo]) => tipo.toUpperCase() !== 'SIN_CLASIFICAR')
    .sort((a, b) => b[1] - a[1])
    .map(([tipo, cantidad], indice) => ({ id: tipo, nombre: nombresTipo[tipo.toUpperCase()] ?? tipo.replaceAll('_', ' ').toLowerCase(), cantidad, color: coloresTema[indice % coloresTema.length] }));
  const maxTema = Math.max(1, ...temas.map((item) => item.cantidad));
  const temasIA = (kpis?.temas_principales ?? [])
    .map(({ tema, cantidad }, indice) => ({ id: tema, nombre: tema.charAt(0).toLocaleUpperCase('es') + tema.slice(1), cantidad, color: coloresTema[indice % coloresTema.length] }));
  const maxTemaIA = Math.max(1, ...temasIA.map((item) => item.cantidad));

  // Tasas operativas
  const totalMsgs = kpis?.total_mensajes ?? 0;
  const tasaCoberturaIA = totalMsgs > 0 ? Math.round((analizados / totalMsgs) * 100) : 0;
  const tasaAprobacion =
    (kpis?.activos_generados ?? 0) > 0
      ? Math.round(((kpis?.activos_aprobados ?? 0) / (kpis?.activos_generados ?? 1)) * 100)
      : 0;

  // Segmentos de la Dona con colores y metadatos
  const segmentos = [
    { id: 'positivo', nombre: 'Positivos', valor: pctPos, cantidad: pos, stroke: '#b9e9c5', bgHex: '#b9e9c5' },
    { id: 'neutral', nombre: 'Neutrales', valor: pctNeu, cantidad: neu, stroke: '#a7a79f', bgHex: '#a7a79f' },
    { id: 'negativo', nombre: 'Negativos', valor: pctNeg, cantidad: neg, stroke: '#90a8ed', bgHex: '#90a8ed' },
    { id: 'indeterminado', nombre: 'Indeterminados', valor: pctInd, cantidad: ind, stroke: '#f1f333', bgHex: '#f1f333' },
  ];

  const radio = 62;
  const circunferencia = 2 * Math.PI * radio;
  let acumulado = 0;

  // Segmento actualmente seleccionado en el hover
  const infoSeleccionada = segmentos.find((s) => s.id === segmentoActivo);

  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="dashboard-content analytics-page flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
                Analítica y gráficas
              </h1>
              <p className="text-muted-foreground text-sm mt-1">
                Visualización interactiva del sentimiento, del embudo editorial y de la clasificación de mensajes con IA
                {aplicados ? ' · ' + aplicados.length + (aplicados.length === 1 ? ' lote aplicado' : ' lotes aplicados') : ''}.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <SelectorLotes ambitos={ambitos} seleccion={seleccion} setSeleccion={setSeleccion} />

              <button onClick={cargarDatos} className="analytics-refresh btn-secondary" title="Actualizar datos" disabled={cargando} aria-busy={cargando}>
                <RefreshCw className={`w-4 h-4 ${cargando ? 'animate-spin' : ''}`} />
                Actualizar
              </button>
            </div>
          </header>

          {errorLotes && <p role="alert" className="card p-4 mb-5 text-sm text-danger">{errorLotes}</p>}
          {errorCarga && <p role="alert" className="card p-4 mb-5 text-sm text-danger">{errorCarga}</p>}
          {cargando && !kpis ? (
            <div className="card flex items-center justify-center h-80">
              <div className="flex items-center gap-3 text-muted-foreground text-sm">
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                Cargando datos de analítica…
              </div>
            </div>
          ) : !kpis || !resumen ? (
            <p className="card p-6 text-sm text-muted-foreground">Los datos de analítica no están disponibles. Pulsa Actualizar para reintentar.</p>
          ) : aplicados?.length === 0 ? (
            <div className="card p-8 text-center" role="status"><h2 className="text-lg font-bold mb-2">No hay lotes seleccionados</h2><p className="text-sm text-muted-foreground">Selecciona uno o varios lotes y pulsa Actualizar para ver sus gráficas.</p></div>
          ) : (
            <div className="space-y-6" aria-busy={cargando}>
              {/* Tarjetas Superiores de Rendimiento */}
              <div className="analytics-summary-grid grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="card p-5 relative overflow-hidden group hover:border-primary/50 transition-all">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Cobertura de análisis
                    </span>
                    <TrendingUp className="w-4 h-4 text-primary group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {tasaCoberturaIA}%
                    </span>

                  </div>
                  <div className="w-full h-2.5 bg-surface-muted rounded-full overflow-hidden mt-3 p-0.5 border border-border/50">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${tasaCoberturaIA}%` }}
                      transition={{ duration: 0.9, ease: 'easeOut' }}
                      className="h-full bg-[#90a8ed] rounded-full"
                    />
                  </div>
                </div>

                <div className="card p-5 relative overflow-hidden group hover:border-success/50 transition-all">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Tasa de aprobación
                    </span>
                    <Layers className="w-4 h-4 text-[#b9e9c5] group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {tasaAprobacion}%
                    </span>

                  </div>
                  <div className="w-full h-2.5 bg-surface-muted rounded-full overflow-hidden mt-3 p-0.5 border border-border/50">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${tasaAprobacion}%` }}
                      transition={{ duration: 0.9, ease: 'easeOut' }}
                      className="h-full bg-[#b9e9c5] rounded-full"
                    />
                  </div>
                </div>

                <div className="card p-5 relative overflow-hidden group hover:border-danger/50 transition-all">
                  <div className="flex justify-between items-center mb-2">
                    <h2 className="text-lg font-bold text-foreground">Bloqueos</h2>
                    <ShieldAlert className="w-4 h-4 text-[#ff90e8] group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {kpis?.alertas_internas ?? 0}
                    </span>

                  </div>
                  {(kpis?.alertas_internas ?? 0) > 0 && <p className="text-xs text-muted-foreground mt-3 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-[#f1f333]" aria-hidden="true" />
                    Revisa las alertas internas antes de continuar con la publicación.
                  </p>}
                </div>
              </div>

              {/* Fila Central: Gráfica de Dona Interactiva + Embudo */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Gráfica 1: Dona Interactiva de Sentimiento */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="card p-6 flex flex-col justify-between"
                >
                  <div>
                    <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                      <PieChart className="w-5 h-5 text-primary" /> Distribución del sentimiento comunitario
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1">
                      Pasa el cursor sobre los segmentos o la leyenda para explorar el desglose detallado.
                    </p>
                  </div>

                  {analizados === 0 ? (
                    <div className="py-16 text-center text-sm text-subtle-foreground">
                      Aún no hay mensajes analizados en este ámbito para graficar el sentimiento.
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row items-center justify-around gap-6 my-6">
                      {/* Contenedor de la Dona SVG con efectos Hover */}
                      <div className="relative w-48 h-48 flex items-center justify-center group">
                        <svg className="w-full h-full -rotate-90 drop-shadow-md" viewBox="0 0 160 160">
                          <circle
                            cx="80"
                            cy="80"
                            r={radio}
                            fill="transparent"
                            stroke="currentColor"
                            strokeWidth="16"
                            className="text-surface-muted"
                          />
                          {segmentos.map((seg) => {
                            const longitud = (seg.valor / 100) * circunferencia;
                            const dashArray = `${longitud} ${circunferencia}`;
                            const dashOffset = -((acumulado / 100) * circunferencia);
                            acumulado += seg.valor;
                            const isHovered = segmentoActivo === seg.id;

                            return <UiTree key={seg.id}>{(
                              <circle
                                key={seg.id}
                                cx="80"
                                cy="80"
                                r={radio}
                                fill="transparent"
                                stroke={seg.stroke}
                                strokeWidth={isHovered ? '22' : '16'}
                                strokeDasharray={dashArray}
                                strokeDashoffset={dashOffset}
                                strokeLinecap="round"
                                className="transition-all duration-300 cursor-pointer"
                                onMouseEnter={() => setSegmentoActivo(seg.id)}
                                onMouseLeave={() => setSegmentoActivo(null)}
                              />
                            )}</UiTree>;
                          })}
                        </svg>

                        {/* Centro de la Dona Dinámico */}
                        <div
                          className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none"
                          style={{ transition: 'all 0.2s ease' }}
                        >
                          {infoSeleccionada ? (
                            <>
                              <span
                                className="text-xl font-extrabold tabular-nums"
                                style={{ color: infoSeleccionada.stroke }}
                              >
                                {infoSeleccionada.cantidad}
                              </span>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-foreground">
                                {infoSeleccionada.nombre} ({infoSeleccionada.valor}%)
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="text-2xl font-extrabold text-foreground tabular-nums">
                                {analizados}
                              </span>
                              <span className="text-[10px] text-subtle-foreground uppercase tracking-wider font-semibold">
                                Analizados
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Leyendas Interactivas */}
                      <div className="space-y-2.5 w-full sm:w-auto min-w-[210px]">
                        {segmentos.map((seg) => {
                          const isHovered = segmentoActivo === seg.id;
                          return <UiTree key={seg.id}>{(
                            <div
                              key={seg.id}
                              onMouseEnter={() => setSegmentoActivo(seg.id)}
                              onMouseLeave={() => setSegmentoActivo(null)}
                              className={`flex items-center justify-between text-sm px-3 py-2 rounded-xl transition-all duration-200 cursor-pointer ${
                                isHovered
                                  ? 'bg-surface-hover border border-border-strong shadow-sm scale-[1.02]'
                                  : 'hover:bg-surface-hover/50 border border-transparent'
                              }`}
                            >
                              <span className="flex items-center gap-2.5 text-foreground font-medium">
                                <span
                                  className="w-3.5 h-3.5 rounded-full shadow-sm transition-transform duration-200"
                                  style={{
                                    backgroundColor: seg.bgHex,
                                    transform: isHovered ? 'scale(1.25)' : 'scale(1)',
                                  }}
                                />
                                {seg.nombre}
                              </span>
                              <span className="font-bold tabular-nums text-foreground">
                                {seg.cantidad} <span className="text-xs text-subtle-foreground font-normal">({seg.valor}%)</span>
                              </span>
                            </div>
                          )}</UiTree>;
                        })}
                      </div>
                    </div>
                  )}

                  <div className="pt-3 border-t border-border flex justify-between items-center text-xs text-subtle-foreground">
                    <span className="flex items-center gap-1.5">
                      <Info className="w-3.5 h-3.5 text-primary" /> Gráfica interactiva
                    </span>
                    <span>Sin analizar: {resumen?.sin_analizar ?? 0}</span>
                  </div>
                </motion.div>

                {/* Gráfica 2: Embudo de Curaduría con Gradientes */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.08 }}
                  className="card p-6 flex flex-col justify-between"
                >
                  <div>
                    <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-primary" /> Embudo de curaduría de contenidos
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1">
                      Progreso editorial de los borradores generados: {kpis?.activos_generados ?? 0} en total (LinkedIn, preguntas frecuentes y boletines).
                    </p>
                  </div>

                  <div className="space-y-4 my-6">
                    {estadosActivos.map((item) => {
                      const porcentajeBarra = Math.round((item.cantidad / totalActivos) * 100);
                      return <UiTree key={item.etiqueta}>{(
                        <div key={item.etiqueta} className="space-y-1.5 group">
                          <div className="flex justify-between text-xs font-semibold">
                            <span className="text-foreground group-hover:text-primary transition-colors">
                              {item.etiqueta}
                            </span>
                            <span className="text-foreground tabular-nums font-bold">
                              {item.cantidad} ({porcentajeBarra}%)
                            </span>
                          </div>
                          <div className="w-full h-3.5 bg-surface-muted rounded-full overflow-hidden p-0.5 border border-border/50">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.max(item.cantidad > 0 ? 5 : 0, porcentajeBarra)}%` }}
                              transition={{ duration: 0.8, ease: 'easeOut' }}
                              className="h-full rounded-full group-hover:brightness-110 transition-all"
                              style={{ backgroundColor: item.color }}
                            />
                          </div>
                        </div>
                      )}</UiTree>;
                    })}
                  </div>

                  <div className="pt-3 border-t border-border flex justify-between text-xs text-subtle-foreground">
                    <span>Pendientes de revisión: {kpis?.borradores_pendientes ?? 0}</span>
                    <span>Publicación externa: manual</span>
                  </div>
                </motion.div>
              </div>

              {/* Fila Inferior: Volumen de Interacciones con Barras Estilizadas */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
                className="card p-6"
              >
                <h2 className="text-base font-bold text-foreground mb-1">
                  Temas recurrentes de la comunidad
                </h2>
                <p className="text-xs text-muted-foreground mb-5">
                  Temas y tipos de participación más frecuentes en la comunidad: preguntas, consultas, comentarios, situaciones, palabras, etc.
                </p>

                {temas.length === 0 && temasIA.length === 0 ? (
                  <p className="text-sm text-subtle-foreground py-8 text-center">
                    Aún no hay temas ni tipos de participación registrados para los lotes aplicados.
                  </p>
                ) : [
                  { titulo: 'Temas detectados', items: temasIA, maximo: maxTemaIA },
                  { titulo: 'Tipos de participación', items: temas, maximo: maxTema },
                ].filter((grupo) => grupo.items.length > 0).map((grupo) => (
                  <div key={grupo.titulo} className="mb-5 last:mb-0">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-3">{grupo.titulo}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {grupo.items.map(({ id, nombre, cantidad, color }) => {
                      const pct = Math.round((cantidad / grupo.maximo) * 100);
                      return <UiTree key={id}>{(
                        <div
                          key={id}
                          className="p-4 rounded-2xl border border-border bg-surface-muted/30 hover:bg-surface-hover/80 hover:border-border-strong transition-all duration-200 group"
                        >
                          <div className="flex justify-between items-center mb-2.5">
                            <span className="badge-neutral font-bold">
                              {nombre}
                            </span>
                            <span className="text-sm font-extrabold text-foreground tabular-nums">
                              {cantidad} <span className="text-xs font-normal text-muted-foreground">{cantidad === 1 ? 'mensaje' : 'mensajes'}</span>
                            </span>
                          </div>
                          <div className="w-full h-3 bg-surface-muted rounded-full overflow-hidden p-0.5 border border-border/50">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.max(pct > 0 ? 6 : 0, pct)}%` }}
                              transition={{ duration: 0.8, ease: 'easeOut' }}
                              className="h-full rounded-full group-hover:brightness-110 transition-all"
                              style={{ backgroundColor: color }}
                            />
                          </div>
                        </div>
                      )}</UiTree>;
                    })}
                  </div>
                  </div>
                ))}
              </motion.div>
            </div>
          )}
        </main>
      </div>
    </RutaProtegida>
  )}</UiTree>;
}