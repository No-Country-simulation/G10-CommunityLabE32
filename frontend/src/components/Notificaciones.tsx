'use client';

import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { obtenerPendientesCuraduria } from '@/services/api';

// El contador corresponde a los logros pendientes de Curaduría.
export default function Notificaciones() {
  const [pendientes, setPendientes] = useState<number | null>(null);
  useEffect(() => {
    let vigente = true;
    let timer: ReturnType<typeof setTimeout>;
    const consultar = async () => {
      try {
        const cantidad = await obtenerPendientesCuraduria();
        if (vigente) setPendientes(typeof cantidad === 'number' && Number.isSafeInteger(cantidad) && cantidad >= 0 ? cantidad : null);
      } catch { if (vigente) setPendientes(null); }
      finally { if (vigente) timer = setTimeout(consultar, 30000); }
    };
    void consultar();
    return () => { vigente = false; clearTimeout(timer); };
  }, []);
  const etiqueta = pendientes === null ? 'Pendientes de Curaduría: pendiente de conexión' : pendientes === 0 ? 'No hay pendientes de Curaduría' : `${pendientes} ${pendientes === 1 ? 'pendiente' : 'pendientes'} de Curaduría`;
  return <UiTree>{<div className="header-notifications"><Link href="/curaduria?estado=pendientes" onClick={() => window.dispatchEvent(new Event('communitylab-curaduria-pendientes'))} className="notification-bell" aria-label={`${etiqueta}. Ver pendientes de Curaduría`} title={etiqueta}><Bell size={20} aria-hidden="true"/>{pendientes !== null && pendientes > 0 && <span className="notification-count" aria-hidden="true">{pendientes > 99 ? '99+' : pendientes}</span>}</Link><span className="sr-only" role="status" aria-live="polite">{etiqueta}</span></div>}</UiTree>;
}
