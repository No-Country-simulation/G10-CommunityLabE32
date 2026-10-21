'use client';


import UiTree from '@/components/UiTree';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { esVistaLocal } from '@/services/vistaLocal';
import {
  obtenerSesion,
  obtenerMensajes, listarActivos, listarAlertasInternas,
} from '@/services/api';
import {
  Loader2, MessageSquare, Layers, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import CommunityIntro from '@/components/CommunityIntro';
import ResultadosResumen, { type FiltroResumen } from '@/components/ResultadosResumen';

const tonos = {
  info: { fondo: 'bg-info-soft', texto: 'text-info' },
  success: { fondo: 'bg-success-soft', texto: 'text-success' },
  warning: { fondo: 'bg-warning-soft', texto: 'text-warning' },
  danger: { fondo: 'bg-danger-soft', texto: 'text-danger' },
} as const;

export default function CommunityDashboard() {
  const router = useRouter();
  const reducirMovimiento = useReducedMotion();
  const [autorizado, setAutorizado] = useState(false);
  const [totales, setTotales] = useState<Record<FiltroResumen, number | null>>({ mensajes: null, pendientes: null, aprobados: null, alertas: null });
  const [filtro, setFiltro] = useState<FiltroResumen>('mensajes');
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  useEffect(() => {
    // La sesión la decide el servidor (cookie HttpOnly); la vista sin sesión solo existe en `npm run dev` local.
    let vigente = true;
    if (esVistaLocal()) {
      const timer = setTimeout(() => { if (vigente) setAutorizado(true); }, 0);
      return () => { vigente = false; clearTimeout(timer); };
    }
    obtenerSesion()
      .then((usuario) => { if (!vigente) return; if (usuario) setAutorizado(true); else router.replace('/login'); })
      .catch(() => { if (vigente) router.replace('/login'); });
    return () => { vigente = false; };
  }, [router]);

  useEffect(() => {
    if (!autorizado) return;
    let vigente = true;
    const filtros: FiltroResumen[] = ['mensajes', 'pendientes', 'aprobados', 'alertas'];
    Promise.allSettled([
      obtenerMensajes(0, 1),
      listarActivos(1, 1, undefined, undefined, 'generado,revisado'),
      listarActivos(1, 1, 'aprobado'),
      listarAlertasInternas(0, 1),
    ]).then(resultados => {
      if (!vigente) return;
      const datos: Record<FiltroResumen, number | null> = { mensajes: null, pendientes: null, aprobados: null, alertas: null };
      resultados.forEach((resultado, indice) => { if (resultado.status === 'fulfilled') datos[filtros[indice]] = resultado.value.total; });
      setTotales(datos);
      if (resultados.some(resultado => resultado.status === 'rejected')) setErrorCarga('No se pudieron cargar algunas métricas. Puedes seleccionar su tarjeta para reintentar.');
      setCargando(false);
    });
    return () => { vigente = false; };
  }, [autorizado]);

  const actualizarTotal = useCallback((total: number) => {
    setTotales(actual => ({ ...actual, [filtro]: total }));
  }, [filtro]);

  if (!autorizado) {
    return <UiTree>{(
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground text-sm">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          Verificando sesión segura…
        </div>
      </div>
    )}</UiTree>;
  }

  const tarjetas = [
        {
          titulo: 'Total de mensajes',
          filtro: 'mensajes' as FiltroResumen,
          valor: totales.mensajes,
          icono: MessageSquare,
          tono: tonos.info,
        },
        {
          titulo: 'Borradores pendientes',
          filtro: 'pendientes' as FiltroResumen,
          valor: totales.pendientes,
          icono: Layers,
          tono: tonos.info,
        },
        {
          titulo: 'Aprobados',
          filtro: 'aprobados' as FiltroResumen,
          valor: totales.aprobados,
          icono: CheckCircle2,
          tono: tonos.success,
        },
        {
          titulo: 'Alertas internas',
          filtro: 'alertas' as FiltroResumen,
          valor: totales.alertas,
          icono: AlertTriangle,
          tono: tonos.danger,
        },
      ]
;

  return <UiTree>{(
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
        <details className="overview-intro-disclosure"><summary><span translate="no">CommunityLab</span>{' '}<span>Tu comunidad, en contexto · Ver presentación</span></summary><CommunityIntro /></details>
        <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-1.5">
              Centro de operaciones
            </h1>
            <p className="text-muted-foreground text-[15px]">
              Métricas e interacciones procesadas.
            </p>
          </div>
        </header>


        {errorCarga && <p role="alert" className="card p-4 mb-4">{errorCarga}</p>}
        {cargando ? (
          <div className="card flex items-center justify-center h-72">
            <div className="text-subtle-foreground flex items-center gap-3 text-sm">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              Sincronizando datos…
            </div>
          </div>
        ) : (
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }}
            className="space-y-8"
          >
            {(
              <div className="dashboard-metrics grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                {tarjetas.map((t) => {
                  const Icono = t.icono;
                  return <UiTree key={t.titulo}>{(
                    <button type="button" key={t.titulo} className="metric-card card p-5 text-left" aria-pressed={filtro === t.filtro} onClick={() => setFiltro(t.filtro)}>
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${t.tono.fondo}`}>
                          <Icono className={`w-5 h-5 ${t.tono.texto}`} />
                        </div>
                        <span className="text-sm font-medium text-muted-foreground">{t.titulo}</span>
                      </div>
                      <h3 className="text-3xl font-bold text-foreground tabular-nums">{t.valor ?? '—'}</h3>
                    </button>
                  )}</UiTree>;
                })}
              </div>
            )}

            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={filtro}
                initial={{ opacity: 0, y: reducirMovimiento ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reducirMovimiento ? 0 : -4 }}
                transition={{ duration: reducirMovimiento ? 0 : 0.3, ease: 'easeInOut' }}
              >
                <ResultadosResumen filtro={filtro} onTotal={actualizarTotal} />
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}
      </main>
    </div>
  )}</UiTree>;
}
