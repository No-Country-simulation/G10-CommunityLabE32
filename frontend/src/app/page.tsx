'use client';


import UiTree from '@/components/UiTree';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { esVistaLocal } from '@/services/vistaLocal';
import {
  obtenerSesion,
  obtenerResumenSentimiento, listarActivos, listarAlertasInternas,
} from '@/services/api';
import { Loader2 } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import CommunityIntro from '@/components/CommunityIntro';
import ResultadosResumen, { type FiltroResumen } from '@/components/ResultadosResumen';

const TOTALES_VACIOS: Record<FiltroResumen, number | null> = {
  mensajes: null, positivo: null, negativo: null, neutral: null, indeterminado: null, sin_analizar: null,
  pendientes: null, aprobados: null, alertas: null,
};

// El Resumen habla el mismo idioma que Interacciones: total y sentimientos, con sus colores.
const TARJETAS: { titulo: string; filtro: FiltroResumen }[] = [
  { titulo: 'Total de mensajes', filtro: 'mensajes' },
  { titulo: 'Positivos', filtro: 'positivo' },
  { titulo: 'Negativos', filtro: 'negativo' },
  { titulo: 'Neutrales', filtro: 'neutral' },
  { titulo: 'Indeterminados', filtro: 'indeterminado' },
  { titulo: 'Sin analizar', filtro: 'sin_analizar' },
];
// Lo operativo queda en una línea discreta; las alertas internas solo se ven aquí.
const OPERATIVO: { titulo: string; filtro: FiltroResumen }[] = [
  { titulo: 'Borradores pendientes', filtro: 'pendientes' },
  { titulo: 'Aprobados', filtro: 'aprobados' },
  { titulo: 'Alertas internas', filtro: 'alertas' },
];

export default function CommunityDashboard() {
  const router = useRouter();
  const reducirMovimiento = useReducedMotion();
  const [autorizado, setAutorizado] = useState(false);
  const [totales, setTotales] = useState<Record<FiltroResumen, number | null>>(TOTALES_VACIOS);
  const [filtro, setFiltro] = useState<FiltroResumen>('mensajes');
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');
  const resultadosRef = useRef<HTMLDivElement>(null);

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
    Promise.allSettled([
      obtenerResumenSentimiento(),
      listarActivos(1, 1, undefined, undefined, 'generado,revisado'),
      listarActivos(1, 1, 'aprobado'),
      listarAlertasInternas(0, 1),
    ]).then(([sentimiento, pendientes, aprobados, alertas]) => {
      if (!vigente) return;
      const datos = { ...TOTALES_VACIOS };
      if (sentimiento.status === 'fulfilled') {
        const r = sentimiento.value;
        Object.assign(datos, { mensajes: r.total, ...r.por_valor, sin_analizar: r.sin_analizar });
      }
      if (pendientes.status === 'fulfilled') datos.pendientes = pendientes.value.total;
      if (aprobados.status === 'fulfilled') datos.aprobados = aprobados.value.total;
      if (alertas.status === 'fulfilled') datos.alertas = alertas.value.total;
      setTotales(datos);
      if ([sentimiento, pendientes, aprobados, alertas].some(r => r.status === 'rejected')) setErrorCarga('No se pudieron cargar algunas métricas. Puedes seleccionar su tarjeta para reintentar.');
      setCargando(false);
    });
    return () => { vigente = false; };
  }, [autorizado]);

  const actualizarTotal = useCallback((total: number) => {
    setTotales(actual => ({ ...actual, [filtro]: total }));
  }, [filtro]);

  // Elegir una tarjeta cambia los resultados sin desmontarlos (sin saltos) y, si quedan fuera de la
  // vista, se desplaza hacia ellos con suavidad.
  const elegirFiltro = (nuevo: FiltroResumen) => {
    setFiltro(nuevo);
    const resultados = resultadosRef.current;
    if (!resultados) return;
    const { top } = resultados.getBoundingClientRect();
    if (top < 0 || top > window.innerHeight - 160) resultados.scrollIntoView({ behavior: reducirMovimiento ? 'auto' : 'smooth', block: 'start' });
  };

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

  return <UiTree>{(
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
        <div className="overview-intro"><CommunityIntro /></div>
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
            <div>
              <div className="overview-sentiments interaction-stats grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4" role="group" aria-label="Filtrar por sentimiento">
                {TARJETAS.map((t) => (
                  <button type="button" key={t.filtro} data-filtro={t.filtro === 'mensajes' ? 'todos' : t.filtro} className="interaction-stat card px-5 py-4 text-left" aria-pressed={filtro === t.filtro} onClick={() => elegirFiltro(t.filtro)}>
                    <p className="text-xs font-medium uppercase tracking-wider text-subtle-foreground">{t.titulo}</p>
                    <p className="mt-1 text-2xl font-bold tabular-nums">{totales[t.filtro] ?? '—'}</p>
                  </button>
                ))}
              </div>
              <p className="overview-operativo">
                {OPERATIVO.map((o) => (
                  <button type="button" key={o.filtro} aria-pressed={filtro === o.filtro} onClick={() => elegirFiltro(o.filtro)}>
                    <strong className="tabular-nums">{totales[o.filtro] ?? '—'}</strong> <span>{o.titulo}</span>
                  </button>
                ))}
              </p>
            </div>


            <div ref={resultadosRef} className="scroll-mt-6">
              <ResultadosResumen filtro={filtro} onTotal={actualizarTotal} />
            </div>
          </motion.div>
        )}
      </main>
    </div>
  )}</UiTree>;
}
