'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import Link from 'next/link';
import {
  obtenerMensajes,
  obtenerKPIs,
  obtenerAmbitos,
  obtenerSesion,
  Ambito,
  Mensaje,
  DashboardKPIs,
} from '@/services/api';
import {
  Loader2, Wifi, WifiOff, MessageSquare, Layers, CheckCircle2, AlertTriangle, Activity, UploadCloud,
} from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';

const tonos = {
  info: { fondo: 'bg-info-soft', texto: 'text-info' },
  success: { fondo: 'bg-success-soft', texto: 'text-success' },
  warning: { fondo: 'bg-warning-soft', texto: 'text-warning' },
  danger: { fondo: 'bg-danger-soft', texto: 'text-danger' },
} as const;

const sentimentBadge: Record<string, string> = {
  positivo: 'badge-success',
  negativo: 'badge-danger',
};

const itemAnim = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } };

export default function CommunityDashboard() {
  const router = useRouter();
  const [autorizado, setAutorizado] = useState(false);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [ambitos, setAmbitos] = useState<Ambito[]>([]);
  const [ambito, setAmbito] = useState<Ambito | null>(null);
  const [cargando, setCargando] = useState(true);
  const [conectado, setConectado] = useState<boolean | null>(null);

  useEffect(() => {
    // Sesión verificada por el servidor (cookie HttpOnly); sin sesión, al login.
    let vigente = true;
    obtenerSesion()
      .then((usuario) => {
        if (!vigente) return;
        if (usuario) setAutorizado(true);
        else router.replace('/login');
      })
      .catch(() => {
        if (vigente) router.replace('/login');
      });
    return () => { vigente = false; };
  }, [router]);

  useEffect(() => {
    if (!autorizado) return;
    obtenerAmbitos().then(setAmbitos).catch(() => setAmbitos([]));
  }, [autorizado]);

  useEffect(() => {
    if (!autorizado) return;
    let vigente = true;
    // Los textos y autores son solo para operadores: con otro rol (403) se muestran los KPIs sin mensajes.
    const mensajesVisibles = obtenerMensajes(0, 9, undefined, ambito).catch((err) => {
      if (axios.isAxiosError(err) && err.response?.status === 403) return { items: [], total: 0 };
      throw err;
    });
    Promise.all([obtenerKPIs(ambito), mensajesVisibles])
      .then(([kpiData, msgsData]) => {
        if (!vigente) return;
        setKpis(kpiData);
        setMensajes(msgsData.items);
        setConectado(true);
        setCargando(false);
      })
      .catch((err) => {
        if (!vigente) return;
        console.error('Error conectando al backend:', err);
        setConectado(false);
        setCargando(false);
      });
    return () => { vigente = false; };
  }, [ambito, autorizado]);

  if (!autorizado) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground text-sm">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          Verificando sesión segura…
        </div>
      </div>
    );
  }

  const sentimiento = kpis?.sentimiento;
  const tarjetas = kpis
    ? [
        {
          titulo: 'Total mensajes',
          valor: kpis.total_mensajes,
          icono: MessageSquare,
          tono: tonos.info,
          pie: !sentimiento || sentimiento.estado === 'sin_datos' ? (
            <span>Sentimiento: sin datos ({kpis.total_mensajes} sin analizar)</span>
          ) : (
            <div className="flex justify-between gap-2">
              <span className="text-success font-medium">
                +{kpis.distribucion_sentimiento.positivo} positivos
              </span>
              <span className="text-danger font-medium">
                {kpis.distribucion_sentimiento.negativo} negativos
              </span>
              {sentimiento.sin_clasificar > 0 && <span>{sentimiento.sin_clasificar} sin analizar</span>}
            </div>
          ),
        },
        {
          titulo: 'Borradores por revisar',
          valor: kpis.borradores_pendientes,
          icono: Layers,
          tono: tonos.info,
          pie: <span>Generados o revisados, de {kpis.activos_generados} contenidos en total</span>,
        },
        {
          titulo: 'Aprobados',
          valor: kpis.activos_aprobados,
          icono: CheckCircle2,
          tono: tonos.success,
          pie: <span>Sin publicar: la publicación externa aún no está habilitada</span>,
        },
        {
          titulo: 'Alertas internas',
          valor: kpis.alertas_internas,
          icono: AlertTriangle,
          tono: kpis.alertas_internas > 0 ? tonos.danger : tonos.warning,
          pie: <span>Mensajes con bloqueo detectado por el pipeline (no se publican)</span>,
        },
      ]
    : [];

  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
        <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-1.5">
              Centro de Operaciones
            </h1>
            <p className="text-muted-foreground text-[15px]">
              Métricas e interacciones procesadas{ambito ? ` · ${ambito.origen} · ${ambito.periodo}` : ' · todos los lotes'}.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="ambito">Ámbito de las métricas</label>
            <select
              id="ambito"
              className="input py-2! w-auto max-w-full"
              value={ambito ? `${ambito.origen}\u0000${ambito.periodo}` : ''}
              onChange={(e) => {
                const elegido = ambitos.find((a) => `${a.origen}\u0000${a.periodo}` === e.target.value) ?? null;
                setCargando(true);
                setAmbito(elegido);
              }}
            >
              <option value="">Todos los lotes (incluye históricos)</option>
              {ambitos.map((a) => (
                <option key={`${a.origen}\u0000${a.periodo}`} value={`${a.origen}\u0000${a.periodo}`}>
                  {a.origen} · {a.periodo}
                </option>
              ))}
            </select>
            <Link className="btn-secondary" href="/ingesta">
              <UploadCloud className="w-3.5 h-3.5 text-primary" />
              Nueva ingesta
            </Link>
            {conectado === false ? (
              <span className="badge-danger py-1.5! px-3!">
                <WifiOff className="w-3.5 h-3.5" />
                Sin conexión con la API
              </span>
            ) : conectado ? (
              <span className="badge-success py-1.5! px-3!">
                <Wifi className="w-3.5 h-3.5" />
                API conectada
              </span>
            ) : null}
          </div>
        </header>

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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                {tarjetas.map((t) => {
                  const Icono = t.icono;
                  return (
                    <motion.div key={t.titulo} variants={itemAnim} className="card p-5">
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${t.tono.fondo}`}>
                          <Icono className={`w-5 h-5 ${t.tono.texto}`} />
                        </div>
                        <span className="text-sm font-medium text-muted-foreground">{t.titulo}</span>
                      </div>
                      <h3 className="text-3xl font-bold text-foreground tabular-nums">{t.valor}</h3>
                      <div className="mt-3 text-xs text-subtle-foreground">{t.pie}</div>
                    </motion.div>
                  );
                })}
              </div>
            )}

            <div>
              <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-primary" /> Mensajes recientes
              </h2>
              <p className="text-xs text-subtle-foreground -mt-2 mb-4">
                Ordenados por fecha del mensaje. Usa el selector para separar históricos, pruebas y actividad actual.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {mensajes.slice(0, 9).map((msg) => (
                  <motion.div
                    key={msg.id_mensaje}
                    variants={itemAnim}
                    className="card p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-md hover:border-border-strong hover:-translate-y-0.5"
                  >
                    <div>
                      <div className="flex justify-between items-start mb-4">
                        <span className="badge-neutral">{msg.canal}</span>
                        {msg.sentimiento_ref && (
                          <span className={sentimentBadge[msg.sentimiento_ref] ?? 'badge-neutral'}>
                            {msg.sentimiento_ref}
                          </span>
                        )}
                      </div>
                      <p className="text-muted-foreground text-sm leading-relaxed mb-5 line-clamp-4">
                        {msg.texto}
                      </p>
                    </div>
                    <div className="pt-4 border-t border-border flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold shrink-0">
                        {msg.autor.substring(0, 2).toUpperCase()}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">{msg.autor}</span>
                        <span className="text-xs text-subtle-foreground">
                          {new Date(msg.fecha).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}