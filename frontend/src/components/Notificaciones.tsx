'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { obtenerMensajesSinResponder } from '@/services/api';

// El backend puede añadir mensajes_sin_responder a GET /api/dashboard/kpis.
export default function Notificaciones() {
  const [pendientes, setPendientes] = useState<number | null>(null);
  useEffect(() => {
    let vigente = true;
    let timer: ReturnType<typeof setTimeout>;
    const consultar = async () => {
      try {
        const cantidad = await obtenerMensajesSinResponder();
        if (vigente) setPendientes(typeof cantidad === 'number' && Number.isSafeInteger(cantidad) && cantidad >= 0 ? cantidad : null);
      } catch { if (vigente) setPendientes(null); }
      finally { if (vigente) timer = setTimeout(consultar, 30000); }
    };
    void consultar();
    return () => { vigente = false; clearTimeout(timer); };
  }, []);
  const etiqueta = pendientes === null ? 'Mensajes sin responder: pendiente de conexión' : pendientes === 0 ? 'No hay mensajes sin responder' : `${pendientes} mensajes sin responder`;
  return <div className="header-notifications"><Link href="/interacciones" className="notification-bell" aria-label={`${etiqueta}. Ver interacciones`} title={etiqueta}><Bell size={20} aria-hidden="true"/>{pendientes !== null && pendientes > 0 && <span className="notification-count" aria-hidden="true">{pendientes > 99 ? '99+' : pendientes}</span>}</Link><span className="sr-only" role="status" aria-live="polite">{etiqueta}</span></div>;
}
