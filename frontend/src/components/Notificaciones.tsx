'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { obtenerAlertasInternas } from '@/services/api';

// Alertas internas del análisis (GET /api/dashboard/kpis → alertas_internas), revisadas cada 60 s.
export default function Notificaciones() {
  const [alertas, setAlertas] = useState<number | null>(null);
  useEffect(() => {
    let vigente = true;
    let timer: ReturnType<typeof setTimeout>;
    const consultar = async () => {
      try {
        const cantidad = await obtenerAlertasInternas();
        if (vigente) setAlertas(Number.isSafeInteger(cantidad) && cantidad >= 0 ? cantidad : null);
      } catch { if (vigente) setAlertas(null); }
      finally { if (vigente) timer = setTimeout(consultar, 60000); }
    };
    void consultar();
    return () => { vigente = false; clearTimeout(timer); };
  }, []);
  const etiqueta = alertas === null ? 'Alertas internas: no disponibles' : alertas === 0 ? 'Sin alertas internas' : `${alertas} ${alertas === 1 ? 'alerta interna' : 'alertas internas'} que requieren atención`;
  return <div className="header-notifications"><Link href="/interacciones" className="notification-bell" aria-label={`${etiqueta}. Ver interacciones`} title={etiqueta}><Bell size={20} aria-hidden="true"/>{alertas !== null && alertas > 0 && <span className="notification-count" aria-hidden="true">{alertas > 99 ? '99+' : alertas}</span>}</Link><span className="sr-only" role="status" aria-live="polite">{etiqueta}</span></div>;
}
