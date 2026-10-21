'use client';


import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { esVistaLocal } from '@/services/vistaLocal';
import {
  obtenerKPIs,
  obtenerSesion,
  DashboardKPIs,
} from '@/services/api';
import {
  Loader2, MessageSquare, Layers, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { motion } from 'framer-motion';
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
  const [autorizado, setAutorizado] = useState(false);
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
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
    obtenerKPIs().then(datos => { if (vigente) setKpis(datos); })
      .catch(() => { if (vigente) setErrorCarga('No se pudieron cargar las métricas.'); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [autorizado]);

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

  const tarjetas = kpis
    ? [
        {
          titulo: 'Total de mensajes',
          filtro: 'mensajes' as FiltroResumen,
          valor: kpis.total_mensajes,
          icono: MessageSquare,
          tono: tonos.info,
        },
        {
          titulo: 'Borradores pendientes',
          filtro: 'pendientes' as FiltroResumen,
          valor: kpis.borradores_pendientes,
          icono: Layers,
          tono: tonos.info,
        },
        {
          titulo: 'Aprobados',
          filtro: 'aprobados' as FiltroResumen,
          valor: kpis.activos_aprobados,
          icono: CheckCircle2,
          tono: tonos.success,
        },
        {
          titulo: 'Alertas internas',
          filtro: 'alertas' as FiltroResumen,
          valor: kpis.alertas_internas,
          icono: AlertTriangle,
          tono: kpis.alertas_internas > 0 ? tonos.danger : tonos.warning,
        },
      ]
    : [];

  return <UiTree>{(
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
        <CommunityIntro />
        <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-1.5">
              Centro de operaciones
            </h2>
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
            {kpis && (
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
                      <h3 className="text-3xl font-bold text-foreground tabular-nums">{t.valor}</h3>
                    </button>
                  )}</UiTree>;
                })}
              </div>
            )}

            <ResultadosResumen key={filtro} filtro={filtro} />
          </motion.div>
        )}
      </main>
    </div>
  )}</UiTree>;
}
