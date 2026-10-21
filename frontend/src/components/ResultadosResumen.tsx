'use client';

import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import { obtenerMensajes, listarActivos, type Mensaje, type Activo } from '@/services/api';
import { Loader2, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
export type FiltroResumen = 'mensajes' | 'pendientes' | 'aprobados' | 'alertas';
const titulos: Record<FiltroResumen, string> = { mensajes: 'Total de mensajes', pendientes: 'Borradores pendientes', aprobados: 'Aprobados', alertas: 'Alertas internas' };
export default function ResultadosResumen({ filtro }: { filtro: FiltroResumen }) {
  const [pagina, setPagina] = useState(1);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [activos, setActivos] = useState<Activo[]>([]);
  const [paginas, setPaginas] = useState(1);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let vigente = true;
    async function cargar() {
      setCargando(true); setError(''); setMensajes([]); setActivos([]); setPaginas(1);
      try {
        if (filtro === 'mensajes') {
          const datos = await obtenerMensajes((pagina - 1) * 9, 9);
          if (!vigente) return;
          setMensajes(datos.items); setPaginas(Math.max(1, Math.ceil(datos.total / 9)));
        } else if (filtro === 'pendientes') {
          const [generados, revisados] = await Promise.all([listarActivos(pagina, 9, 'generado'), listarActivos(pagina, 9, 'revisado')]);
          if (!vigente) return;
          setActivos([...generados.items, ...revisados.items]);
          setPaginas(Math.max(1, generados.total_pages, revisados.total_pages));
        } else if (filtro === 'aprobados') {
          const datos = await listarActivos(pagina, 9, 'aprobado');
          if (!vigente) return;
          setActivos(datos.items); setPaginas(Math.max(1, datos.total_pages));
        }
      } catch { if (vigente) setError('No se pudo cargar el contenido. Inténtalo de nuevo.'); }
      finally { if (vigente) setCargando(false); }
    }
    cargar();
    return () => { vigente = false; };
  }, [filtro, pagina]);
  return <UiTree>{<section aria-labelledby="resultados-resumen" aria-live="polite">
    <h2 id="resultados-resumen" className="text-lg font-bold mb-4">{titulos[filtro]}</h2>
    {cargando ? <div className="card p-8 flex justify-center"><Loader2 className="w-5 h-5 animate-spin" aria-label="Cargando contenido" /></div> : error ? <p role="alert" className="card p-6 text-sm">{error}</p> : filtro === 'alertas' ? <div className="card p-6 flex items-start gap-3"><AlertTriangle className="w-5 h-5 text-[#f1f333] shrink-0"/><p className="text-sm text-muted-foreground">El detalle de las alertas internas todavía no está disponible.</p></div> : <>
      {mensajes.length === 0 && activos.length === 0 && <p className="card p-6 text-sm text-muted-foreground">No hay contenido disponible en esta categoría.</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {mensajes.map(msg => <article key={msg.id_mensaje} className="message-card card p-5 flex flex-col justify-between"><div><span className="badge-neutral" translate="no">{msg.canal}</span><p className="text-sm text-muted-foreground mt-4 mb-5 whitespace-pre-wrap" translate="no">{msg.texto}</p></div><div className="pt-4 border-t border-border text-xs"><strong translate="no">{msg.autor}</strong><p className="text-muted-foreground mt-1">{msg.fecha ? new Date(msg.fecha).toLocaleDateString('es') : 'Sin fecha'}</p></div></article>)}
        {activos.map(item => <article key={item.id_activo} className="message-card card p-5"><div className="flex justify-between gap-2 mb-4"><span className="badge-neutral">{item.formato}</span><span className="badge-neutral">{item.estado === 'generado' ? 'Generado' : item.estado === 'revisado' ? 'Revisado' : 'Aprobado'}</span></div><h3 className="font-bold mb-3" translate="no">{item.titulo}</h3><p className="text-sm text-muted-foreground whitespace-pre-wrap" translate="no">{item.copy}</p></article>)}
      </div>
      {paginas > 1 && <nav aria-label="Páginas de resultados" className="flex justify-end items-center gap-3 mt-5"><button className="btn-secondary" aria-label="Página anterior" disabled={pagina === 1} onClick={() => setPagina(p => p - 1)}><ChevronLeft size={16}/></button><span className="text-sm">Página {pagina} de {paginas}</span><button className="btn-secondary" aria-label="Página siguiente" disabled={pagina >= paginas} onClick={() => setPagina(p => p + 1)}><ChevronRight size={16}/></button></nav>}
    </>}
  </section>}</UiTree>;
}
