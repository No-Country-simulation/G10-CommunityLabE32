'use client';

import { useEffect, useState } from 'react';
import { obtenerMensajes, obtenerKPIs, Mensaje, DashboardKPIs } from '@/services/api';
import {
  Loader2, Wifi, MessageSquare, Layers, CheckCircle2, AlertTriangle, Activity,
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
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [cargando, setCargando] = useState(true);
  const [cargandoMock, setCargandoMock] = useState(false);

  useEffect(() => {
    Promise.all([obtenerKPIs(), obtenerMensajes()])
      .then(([kpiData, msgsData]) => {
        setKpis(kpiData);
        setMensajes(msgsData.items);
        setCargando(false);
      })
      .catch((err) => {
        console.error('Error conectando al backend:', err);
        setCargando(false);
      });
  }, []);

  // Funcionalidad de pruebas de Tareck preservada
  const probarApiBackend = async () => {
    setCargandoMock(true);
    try {
      const respuesta = await fetch('/api/v1/procesamientos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origen_comunidad: 'discord_comunidad_alura',
          periodo_referencia: '2026-W38',
          interacciones: [
            'Conseguí mi primer empleo como Dev Jr.',
            '¿Cómo configuro reintentos en LangGraph?',
            'Tengo la misma duda sobre reintentos.',
            'Participé en una mentoría de portafolios.',
            'Esta semana compartimos avances de OCI.',
            'Tengo un bloqueo con un timeout de OCI.',
          ].map((texto, index) => ({
            id: `m-0${index + 1}`,
            autor: `persona_demo_${index + 1}`,
            canal: 'pruebas',
            fecha: '2026-09-23T10:00:00Z',
            texto,
          })),
        }),
      });

      if (!respuesta.ok) throw new Error('Error en la respuesta del backend');
      alert('Respuesta de demostración recibida. Esta prueba no guarda datos.');
      window.location.reload();
    } catch {
      alert('No se pudo consultar el backend. Revisa que los servicios locales estén disponibles.');
    } finally {
      setCargandoMock(false);
    }
  };

  const tarjetas = kpis
    ? [
        {
          titulo: 'Total mensajes',
          valor: kpis.total_mensajes,
          icono: MessageSquare,
          tono: tonos.info,
          pie: (
            <div className="flex justify-between">
              <span className="text-success font-medium">
                +{kpis.distribucion_sentimiento?.positivo || 0} positivos
              </span>
              <span className="text-danger font-medium">
                {kpis.distribucion_sentimiento?.negativo || 0} quejas
              </span>
            </div>
          ),
        },
        {
          titulo: 'Borradores IA',
          valor: kpis.activos_generados,
          icono: Layers,
          tono: tonos.info,
          pie: <span>Activos listos para revisión en el panel</span>,
        },
        {
          titulo: 'Publicaciones',
          valor: kpis.activos_aprobados,
          icono: CheckCircle2,
          tono: tonos.success,
          pie: <span>Aprobados listos para OCI Storage</span>,
        },
        {
          titulo: 'Alertas internas',
          valor: kpis.alertas_internas,
          icono: AlertTriangle,
          tono: kpis.alertas_internas > 0 ? tonos.danger : tonos.warning,
          pie: <span>Bloqueos que requieren atención manual</span>,
        },
      ]
    : [];

  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="flex-1 min-w-0 p-6 md:p-10 h-screen overflow-y-auto">
        <header className="mb-8 flex flex-wrap justify-between items-end gap-4">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground mb-1.5">
              Centro de Operaciones
            </h1>
            <p className="text-muted-foreground text-[15px]">
              Métricas en tiempo real e interacciones procesadas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={probarApiBackend} disabled={cargandoMock} className="btn-secondary">
              {cargandoMock ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Activity className="w-3.5 h-3.5 text-primary" />
              )}
              Test Ingesta (Tareck)
            </button>
            <span className="badge-success py-1.5! px-3!">
              <Wifi className="w-3.5 h-3.5" />
              API conectada
            </span>
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
                <Activity className="w-5 h-5 text-primary" /> Flujo en tiempo real
              </h2>
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