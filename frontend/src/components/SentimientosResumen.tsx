'use client';

import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { obtenerResumenSentimiento, type FiltroSentimiento, type ResumenSentimiento } from '@/services/api';

// Mismas tarjetas y colores que Interacciones; cada una abre Interacciones con ese filtro aplicado.
export default function SentimientosResumen() {
  const [resumen, setResumen] = useState<ResumenSentimiento | null>(null);

  useEffect(() => {
    let vigente = true;
    obtenerResumenSentimiento()
      .then((data) => { if (vigente) setResumen(data); })
      .catch((error) => console.error('Error al cargar el resumen de sentimiento:', error));
    return () => { vigente = false; };
  }, []);

  const tarjetas: { filtro: FiltroSentimiento; etiqueta: string; valor: number | string }[] = [
    { filtro: 'positivo', etiqueta: 'Positivos', valor: resumen?.por_valor.positivo ?? '—' },
    { filtro: 'negativo', etiqueta: 'Negativos', valor: resumen?.por_valor.negativo ?? '—' },
    { filtro: 'neutral', etiqueta: 'Neutrales', valor: resumen?.por_valor.neutral ?? '—' },
    { filtro: 'indeterminado', etiqueta: 'Indeterminados', valor: resumen?.por_valor.indeterminado ?? '—' },
    { filtro: 'sin_analizar', etiqueta: 'Sin analizar', valor: resumen?.sin_analizar ?? '—' },
  ];

  return <UiTree>{(
    <section className="overview-sentiments" aria-labelledby="titulo-sentimientos-resumen">
      <h2 id="titulo-sentimientos-resumen" className="text-lg font-bold mb-4">Sentimiento de la comunidad</h2>
      <div className="interaction-stats grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
        {tarjetas.map((t) => (
          <Link key={t.filtro} href={`/interacciones?sentimiento=${t.filtro}`} data-filtro={t.filtro}
            className="interaction-stat card px-5 py-4 text-left">
            <p className="text-xs font-medium uppercase tracking-wider text-subtle-foreground">{t.etiqueta}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{t.valor}</p>
          </Link>
        ))}
      </div>
    </section>
  )}</UiTree>;
}
