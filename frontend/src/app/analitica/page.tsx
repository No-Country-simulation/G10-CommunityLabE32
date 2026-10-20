'use client';

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
  Sparkles,
  Loader2,
  RefreshCw,
  Info,
} from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import RutaProtegida from '@/components/RutaProtegida';

export default function AnaliticaPage() {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [resumen, setResumen] = useState<ResumenSentimiento | null>(null);
  const [ambitos, setAmbitos] = useState<Ambito[]>([]);
  const [ambito, setAmbito] = useState<Ambito | null>(null);
  const [cargando, setCargando] = useState(true);

  // Estado para interactividad de la dona (hover en segmentos o leyendas)
  const [segmentoActivo, setSegmentoActivo] = useState<string | null>(null);

  useEffect(() => {
    obtenerAmbitos().then(setAmbitos).catch(() => setAmbitos([]));
  }, []);

  useEffect(() => {
    let montado = true;
    const ejecutarCarga = async () => {
      setCargando(true);
      try {
        const [kpiData, resData] = await Promise.all([
          obtenerKPIs(ambito),
          obtenerResumenSentimiento(undefined, ambito),
        ]);
        if (!montado) return;
        setKpis(kpiData);
        setResumen(resData);
      } catch (err) {
        console.error('Error cargando analítica:', err);
      } finally {
        if (montado) setCargando(false);
      }
    };

    ejecutarCarga();
    return () => {
      montado = false;
    };
  }, [ambito]);

  // Función auxiliar por si se presiona el botón "Actualizar" de la interfaz
  const cargarDatos = () => {
    setCargando(true);
    Promise.all([obtenerKPIs(ambito), obtenerResumenSentimiento(undefined, ambito)])
      .then(([kpiData, resData]) => {
        setKpis(kpiData);
        setResumen(resData);
        setCargando(false);
      })
      .catch((err) => {
        console.error('Error cargando analítica:', err);
        setCargando(false);
      });
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
  const pctInd = analizados > 0 ? Math.max(0, 100 - pctPos - pctNeu - pctNeg) : 0;

  // Embudo de Curaduría
  const estadosActivos = [
    {
      etiqueta: 'Indeterminados',
      cantidad: kpis?.activos_por_estado?.generado ?? 0,
      color: '#f1f333',
    },
    {
      etiqueta: 'Neutrales',
      cantidad: kpis?.activos_por_estado?.revisado ?? 0,
      color: '#90a8ed',
    },
    {
      etiqueta: 'Positivos',
      cantidad: kpis?.activos_por_estado?.aprobado ?? 0,
      color: '#b9e9c5',
    },
    {
      etiqueta: 'Negativos',
      cantidad: kpis?.activos_por_estado?.rechazado ?? 0,
      color: '#ff90e8',
    },
  ];
  const totalActivos = Math.max(1, kpis?.activos_generados ?? 1);

  // Tipos de mensajes
  const tiposEntries = Object.entries(kpis?.mensajes_por_tipo ?? {}).sort((a, b) => b[1] - a[1]);
  const etiquetasTipo: Record<string, string> = {
    PREGUNTA_TECNICA: 'Pregunta técnica',
    CONSULTA_NEGOCIO: 'Consulta de negocio',
    SIN_CLASIFICAR: 'Sin clasificar',
    LOGRO: 'Logro',
  };
  const coloresCategoria = ['#ff90e8', '#f1f333', '#90a8ed', '#b9e9c5'];
  const maxTipo = Math.max(1, ...tiposEntries.map(([, v]) => v));

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
    { id: 'neutral', nombre: 'Neutrales', valor: pctNeu, cantidad: neu, stroke: '#90a8ed', bgHex: '#90a8ed' },
    { id: 'negativo', nombre: 'Negativos', valor: pctNeg, cantidad: neg, stroke: '#ff90e8', bgHex: '#ff90e8' },
    { id: 'indeterminado', nombre: 'Indeterminados', valor: pctInd, cantidad: ind, stroke: '#f1f333', bgHex: '#f1f333' },
  ];

  const radio = 62;
  const circunferencia = 2 * Math.PI * radio;
  let acumulado = 0;

  // Segmento actualmente seleccionado en el hover
  const infoSeleccionada = segmentos.find((s) => s.id === segmentoActivo);

  return (
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="dashboard-content analytics-page flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-soft text-primary text-xs font-bold mb-2 shadow-sm">
                <Sparkles className="w-3.5 h-3.5" /> Equipo 32
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
                Analítica y gráficas
              </h1>
              <p className="text-muted-foreground text-sm mt-1">
                Visualización interactiva de sentimiento, embudo editorial y clasificación de mensajes con IA
                {ambito ? ` · ${ambito.origen} (${ambito.periodo})` : ' · histórico global'}.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <select
                aria-label="Filtrar por ámbito de lotes"
                className="input py-2! w-auto"
                value={ambito ? `${ambito.origen}\u0000${ambito.periodo}` : ''}
                onChange={(e) => {
                  const elegido =
                    ambitos.find((a) => `${a.origen}\u0000${a.periodo}` === e.target.value) ?? null;
                  setAmbito(elegido);
                }}
              >
                <option value="">Todos los lotes (global)</option>
                {ambitos.map((a) => (
                  <option
                    key={`${a.origen}\u0000${a.periodo}`}
                    value={`${a.origen}\u0000${a.periodo}`}
                  >
                    {a.origen} · {a.periodo}
                  </option>
                ))}
              </select>

              <button onClick={cargarDatos} className="analytics-refresh btn-secondary" title="Actualizar datos" disabled={cargando} aria-busy={cargando}>
                <RefreshCw className={`w-4 h-4 ${cargando ? 'animate-spin' : ''}`} />
                Actualizar
              </button>
            </div>
          </header>

          {cargando ? (
            <div className="card flex items-center justify-center h-80">
              <div className="flex items-center gap-3 text-muted-foreground text-sm">
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                Cargando datos de analítica…
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Tarjetas Superiores de Rendimiento */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="card p-5 relative overflow-hidden group hover:border-primary/50 transition-all">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Cobertura del análisis con IA
                    </span>
                    <TrendingUp className="w-4 h-4 text-primary group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {tasaCoberturaIA}%
                    </span>
                    <span className="text-xs text-subtle-foreground">
                      ({analizados} de {totalMsgs} mensajes)
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
                      Tasa de aprobación editorial
                    </span>
                    <Layers className="w-4 h-4 text-[#b9e9c5] group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {tasaAprobacion}%
                    </span>
                    <span className="text-xs text-subtle-foreground">
                      ({kpis?.activos_aprobados ?? 0} de {kpis?.activos_generados ?? 0} activos)
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
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Bloqueos y alertas internas
                    </span>
                    <ShieldAlert className="w-4 h-4 text-[#ff90e8] group-hover:scale-110 transition-transform" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-foreground tabular-nums">
                      {kpis?.alertas_internas ?? 0}
                    </span>
                    <span className="text-xs text-subtle-foreground">
                      alertas registradas
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-3">
                    Revisa las alertas internas antes de continuar con la publicación.
                  </p>
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
                      Pasa el cursor sobre los segmentos o las leyendas para explorar el desglose detallado.
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

                            return (
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
                            );
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
                          return (
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
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div className="pt-3 border-t border-border flex justify-between items-center text-xs text-subtle-foreground">
                    <span className="flex items-center gap-1.5">
                      <Info className="w-3.5 h-3.5 text-primary" /> Gráfica SVG interactiva
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
                      Progreso editorial de los {kpis?.activos_generados ?? 0} borradores generados (LinkedIn, preguntas frecuentes y boletines).
                    </p>
                  </div>

                  <div className="space-y-4 my-6">
                    {estadosActivos.map((item) => {
                      const porcentajeBarra = Math.round((item.cantidad / totalActivos) * 100);
                      return (
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
                      );
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
                  Volumen de interacciones por categoría o tipo
                </h2>
                <p className="text-xs text-muted-foreground mb-5">
                  Cantidad de mensajes importados según su categoría.
                </p>

                {tiposEntries.length === 0 ? (
                  <p className="text-sm text-subtle-foreground py-8 text-center">
                    No hay interacciones registradas en este ámbito todavía.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tiposEntries.map(([tipo, cantidad], indice) => {
                      const pct = Math.round((cantidad / maxTipo) * 100);
                      return (
                        <div
                          key={etiquetasTipo[tipo.toUpperCase()] ?? tipo.replaceAll('_', ' ')}
                          className="p-4 rounded-2xl border border-border bg-surface-muted/30 hover:bg-surface-hover/80 hover:border-border-strong transition-all duration-200 group"
                        >
                          <div className="flex justify-between items-center mb-2.5">
                            <span className="badge-neutral font-bold">
                              {tipo}
                            </span>
                            <span className="text-sm font-extrabold text-foreground tabular-nums">
                              {cantidad} <span className="text-xs font-normal text-muted-foreground">mensajes</span>
                            </span>
                          </div>
                          <div className="w-full h-3 bg-surface-muted rounded-full overflow-hidden p-0.5 border border-border/50">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.max(pct > 0 ? 6 : 0, pct)}%` }}
                              transition={{ duration: 0.8, ease: 'easeOut' }}
                              className="h-full rounded-full group-hover:brightness-110 transition-all"
                              style={{ backgroundColor: coloresCategoria[indice % coloresCategoria.length] }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            </div>
          )}
        </main>
      </div>
    </RutaProtegida>
  );
}