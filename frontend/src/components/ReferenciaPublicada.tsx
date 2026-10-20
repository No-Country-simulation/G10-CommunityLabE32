'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Info } from 'lucide-react';
import { esReferenciaPublicada } from '@/services/referenciaPublicada';
export default function ReferenciaPublicada() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVisible(esReferenciaPublicada()), 0); return () => clearTimeout(t); }, []);
  if (!visible || !['/','/analitica','/interacciones','/curaduria'].includes(pathname)) return null;
  return <aside className="referencia-publicada" aria-label="Origen de los datos"><Info size={14}/><span>Vista local · contenido de la web publicada. {pathname === '/curaduria' ? 'Muestra de 4 borradores de solo lectura; algunas fuentes y banners no están incluidos.' : pathname === '/interacciones' ? 'Muestra de 10 mensajes; las métricas resumen los 472 originales.' : 'Datos de muestra capturados; no se actualizan en tiempo real.'}</span></aside>;
}
