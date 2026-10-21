'use client';


import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  MessagesSquare, Loader2, CheckCircle2, XCircle, Clock, ArrowRight, AlertTriangle, Radio,
} from 'lucide-react';
import {
  describirError, obtenerEstadoPendientes, solicitarProcesarPendientes,
  ErrorLegible, EstadoPendientes, EstadoSolicitud, SOLICITUD_ABIERTA,
} from '@/services/api';
import TokenOperador from '@/components/TokenOperador';

const ETIQUETA: Record<EstadoSolicitud, string> = {
  pendiente: 'Esperando al puente de Discord',
  tomada: 'El puente está preparando los lotes',
  en_curso: 'Procesando lotes parciales',
  sin_pendientes: 'No había mensajes nuevos',
  completada: 'Borradores listos para curaduría',
  completada_con_errores: 'Terminó con errores',
  cancelada: 'Cancelada',
};
const ETIQUETA_TRABAJO: Record<string, string> = {
  recibido: 'En cola', procesando: 'Procesando', terminado: 'Terminado', error: 'Con error',
};

// Procesa los mensajes de Discord pendientes sin cerrar la semana: el bot sigue respondiendo y
// alertando en tiempo real; esto solo adelanta los borradores. El cierre semanal no cambia.
export default function ProcesarPendientes() {
  const [estado, setEstado] = useState<EstadoPendientes | null>(null);
  const [error, setError] = useState<ErrorLegible | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [refresco, setRefresco] = useState(0);
  const enviandoRef = useRef(false);

  const solicitud = estado?.solicitud ?? null;
  const abierta = !!solicitud && SOLICITUD_ABIERTA.includes(solicitud.estado);

  // Consulta el avance mientras haya una solicitud abierta; si no, una vez.
  useEffect(() => {
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    const controlador = new AbortController();
    const consultar = async () => {
      try {
        const actual = await obtenerEstadoPendientes(controlador.signal);
        if (!vigente) return;
        setEstado(actual);
        if (actual.solicitud && SOLICITUD_ABIERTA.includes(actual.solicitud.estado)) {
          temporizador = setTimeout(consultar, 4000);
        }
      } catch {
        if (vigente) temporizador = setTimeout(consultar, 15000);
      }
    };
    consultar();
    return () => { vigente = false; controlador.abort(); if (temporizador) clearTimeout(temporizador); };
  }, [refresco]);

  const procesar = async () => {
    if (enviandoRef.current) return; // evita doble envío antes del re-render
    enviandoRef.current = true;
    setEnviando(true);
    setError(null);
    try {
      const nueva = await solicitarProcesarPendientes();
      setEstado(prev => prev ? { ...prev, solicitud: nueva } : prev);
      setRefresco(n => n + 1);
    } catch (e) {
      setError(describirError(e));
    } finally {
      enviandoRef.current = false;
      setEnviando(false);
    }
  };

  const puente = estado?.puente ?? null;
  const terminados = solicitud?.lotes.filter(l => l.trabajo_estado === 'terminado' && l.activos > 0) ?? [];

  return <UiTree>{(
    <section aria-live="polite" className="discord-pending-card card p-5 sm:p-6 min-w-0">
      <h2 className="text-[15px] font-semibold text-foreground mb-1 flex items-center gap-2">
        <MessagesSquare className="w-4 h-4 text-primary" /> Procesar mensajes pendientes de Discord
      </h2>
      <p className="text-sm text-muted-foreground">
        Genera borradores con los mensajes nuevos sin cerrar la semana. Las dudas y alertas del bot siguen en tiempo real.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
        <span className={puente?.activo ? 'badge-success' : 'badge-neutral'}>
          <Radio className="w-3 h-3" /> {puente ? (puente.activo ? 'Puente activo' : 'Puente sin señal reciente') : 'Puente sin datos'}
        </span>
        {puente && (
          <span className={puente.pendientes > 0 ? 'badge-warning' : 'badge-neutral'}>
            {puente.pendientes} mensaje(s) pendiente(s)
          </span>
        )}
      </div>

      {solicitud && (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-4 pt-4 border-t border-border text-sm">
          <p className="flex items-center gap-2 font-medium text-foreground">
            {abierta ? <Loader2 className="w-4 h-4 animate-spin text-primary" />
              : solicitud.estado === 'completada_con_errores' ? <XCircle className="w-4 h-4 text-danger" />
              : solicitud.estado === 'sin_pendientes' ? <Clock className="w-4 h-4 text-subtle-foreground" />
              : <CheckCircle2 className="w-4 h-4 text-success" />}
            {solicitud.estado === 'completada' && solicitud.activos_creados === 0
              ? 'Procesado: ningún mensaje generó borradores' : ETIQUETA[solicitud.estado]}
          </p>
          <p className="mt-1 text-xs text-muted-foreground font-mono break-all">{solicitud.id}</p>
          {solicitud.lotes.length > 0 && (
            <>
              <p className="mt-2 text-xs text-muted-foreground">
                {solicitud.mensajes_nuevos} mensaje(s) nuevo(s)
                {solicitud.mensajes_contexto > 0 && ` · ${solicitud.mensajes_contexto} de contexto ya procesado`}
                {' · '}{solicitud.activos_creados} borrador(es)
              </p>
              <ul className="mt-2 flex flex-col gap-1.5">
                {solicitud.lotes.map((l, i) => (
                  <li key={l.trabajo ?? i} className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="badge-neutral">{l.periodo}</span>
                    <span className="text-muted-foreground">{l.nuevos} nuevos</span>
                    <span className={l.trabajo_estado === 'terminado' ? 'badge-success'
                      : l.trabajo_estado === 'error' || l.estado === 'error' || l.estado === 'rechazado' ? 'badge-danger' : 'badge-info'}>
                      {ETIQUETA_TRABAJO[l.trabajo_estado ?? ''] ?? (l.estado === 'rechazado' ? 'Rechazado' : 'Enviando')}
                    </span>
                    {l.trabajo_estado === 'terminado' && l.alertas > 0 && (
                      <span className="text-subtle-foreground">{l.alertas} alerta(s) interna(s)</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
          {solicitud.trabajos_error > 0 && (
            <p className="mt-2 text-xs text-warning flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              Los mensajes de los lotes con error vuelven a quedar pendientes para la próxima solicitud.
            </p>
          )}
          {terminados.length === 1 && terminados[0].trabajo && (
            <Link href={`/curaduria?trabajo=${encodeURIComponent(terminados[0].trabajo)}`} className="btn-secondary w-fit mt-3">
              Ver borradores <ArrowRight className="w-4 h-4" />
            </Link>
          )}
          {terminados.length > 1 && (
            <Link href="/curaduria" className="btn-secondary w-fit mt-3">
              Ver borradores en curaduría <ArrowRight className="w-4 h-4" />
            </Link>
          )}
        </motion.div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-danger flex items-start gap-2">
          <XCircle className="w-4 h-4 mt-0.5 shrink-0" /> <span><strong>{error.titulo}.</strong> {error.mensaje}</span>
        </p>
      )}

      <TokenOperador className="mt-4" />
      <button
        onClick={procesar}
        disabled={enviando || abierta}
        className={`${enviando || abierta ? 'btn-secondary' : 'btn-primary'} w-full mt-3`}
      >
        {enviando ? 'Solicitando…' : abierta ? 'Procesamiento en curso…' : 'Procesar pendientes'}
      </button>
      <p className="mt-2 text-xs text-subtle-foreground">
        Sin mensajes nuevos no se consume IA. Ningún borrador se publica sin revisión.
      </p>
    </section>
  )}</UiTree>;
}
