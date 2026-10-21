'use client';

import UiTree from '@/components/UiTree';
import VerMensaje from '@/components/VerMensaje';
import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { obtenerMensajes, listarActivos, listarAlertasInternas, type Mensaje, type Activo, type AlertaInterna } from '@/services/api';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
export type FiltroResumen = 'mensajes' | 'pendientes' | 'aprobados' | 'alertas';
const POR_PAGINA = 9;
const titulos: Record<FiltroResumen, string> = { mensajes: 'Total de mensajes', pendientes: 'Borradores pendientes', aprobados: 'Aprobados', alertas: 'Alertas internas' };
const colores = { mensajes: '#ff90e8', pendientes: '#f1f333', aprobados: '#b9e9c5', alertas: '#90a8ed' };
// Etiqueta de cada mensaje: su relación con borradores y alertas o, si no tiene, su tipo de participación.
const relacionMensaje: Record<Exclude<FiltroResumen, 'mensajes'>, string> = { pendientes: 'Con borrador pendiente', aprobados: 'Con borrador aprobado', alertas: 'Con alerta interna' };
const tiposMensaje: Record<string, string> = { logro: 'Logro', duda: 'Duda', bloqueo: 'Bloqueo', comentario: 'Comentario', testimonio: 'Testimonio', pregunta_tecnica: 'Duda', consulta_negocio: 'Consulta' };
function etiquetaMensaje(mensaje: Mensaje): string {
  const categoria = categoriaMensaje(mensaje);
  return categoria === 'mensajes' ? tiposMensaje[mensaje.tipo ?? ''] ?? 'Sin clasificar' : relacionMensaje[categoria];
}
function categoriaMensaje(mensaje: Mensaje): FiltroResumen {
  if (mensaje.alerta_interna === true) return 'alertas';
  if (mensaje.estado_borrador === 'aprobado') return 'aprobados';
  if (mensaje.estado_borrador === 'pendiente') return 'pendientes';
  return 'mensajes';
}
function fechaLegible(fecha: string | null): string {
  if (!fecha) return 'Sin fecha';
  const valor = new Date(fecha);
  return Number.isNaN(valor.getTime()) ? 'Sin fecha' : valor.toLocaleDateString('es');
}
const claseTarjeta = 'message-card card min-w-0 p-5 flex flex-col justify-between break-words';
export default function ResultadosResumen({ filtro, onTotal }: { filtro: FiltroResumen; onTotal: (total: number) => void }) {
  const [pagina, setPagina] = useState(1);
  const [filtroMostrado, setFiltroMostrado] = useState(filtro);
  // Cambiar de tarjeta vuelve a la primera página (ajuste durante el render, sin efecto extra).
  if (filtroMostrado !== filtro) { setFiltroMostrado(filtro); setPagina(1); }
  const tituloRef = useRef<HTMLHeadingElement>(null);
  const reducirMovimiento = useReducedMotion();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [activos, setActivos] = useState<Activo[]>([]);
  const [alertas, setAlertas] = useState<AlertaInterna[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [intento, setIntento] = useState(0);
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  useEffect(() => {
    let vigente = true;
    async function cargar() {
      setCargando(true); setError('');
      try {
        let cantidad: number;
        if (filtro === 'mensajes') {
          const datos = await obtenerMensajes((pagina - 1) * POR_PAGINA, POR_PAGINA);
          if (!vigente) return;
          setMensajes(datos.items); setActivos([]); setAlertas([]); cantidad = datos.total;
        } else if (filtro === 'alertas') {
          const datos = await listarAlertasInternas((pagina - 1) * POR_PAGINA, POR_PAGINA);
          if (!vigente) return;
          setAlertas(datos.items); setMensajes([]); setActivos([]); cantidad = datos.total;
        } else {
          const datos = filtro === 'pendientes'
            ? await listarActivos(pagina, POR_PAGINA, undefined, undefined, 'generado,revisado')
            : await listarActivos(pagina, POR_PAGINA, 'aprobado');
          if (!vigente) return;
          setActivos(datos.items); setMensajes([]); setAlertas([]); cantidad = datos.total;
        }
        setTotal(cantidad); onTotal(cantidad);
      } catch { if (vigente) setError('No se pudo cargar el contenido. Inténtalo de nuevo.'); }
      finally { if (vigente) setCargando(false); }
    }
    void cargar();
    return () => { vigente = false; };
  }, [filtro, pagina, intento, onTotal]);
  const hayContenido = mensajes.length + activos.length + alertas.length > 0;
  const irAPagina = (nueva: number) => {
    setPagina(nueva);
    // Si el título quedó arriba de la vista (paginación al final de la lista), se vuelve a él con suavidad.
    const titulo = tituloRef.current;
    if (titulo && titulo.getBoundingClientRect().top < 0) titulo.scrollIntoView({ behavior: reducirMovimiento ? 'auto' : 'smooth', block: 'start' });
  };
  return <UiTree><section aria-labelledby="resultados-resumen" aria-live="polite" aria-busy={cargando} style={{ overflowAnchor: 'none' }}>
    <h2 id="resultados-resumen" ref={tituloRef} className="text-lg font-bold mb-4 scroll-mt-6">{titulos[filtro]}</h2>
    {cargando && !hayContenido ? <div className="card p-8 flex justify-center"><Loader2 className="w-5 h-5 animate-spin" aria-label="Cargando contenido" /></div> : error ? <div role="alert" className="card p-6 text-sm"><p>{error}</p><button type="button" className="btn-secondary mt-3" onClick={() => setIntento(i => i + 1)}>Reintentar</button></div> : <>
      {total === 0 && !cargando && <p className="card p-6 text-sm text-muted-foreground">No hay contenido disponible en esta categoría.</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 transition-opacity duration-200" style={{ opacity: cargando ? 0.45 : 1 }}>
        {mensajes.map(msg => <article key={msg.id_mensaje} className={claseTarjeta} style={{ borderTopColor: colores[categoriaMensaje(msg)], overflowWrap: 'anywhere' }}><div><div className="flex flex-wrap gap-2"><span className="badge-neutral" translate="no">{msg.canal}</span><span className="badge-neutral">{etiquetaMensaje(msg)}</span></div><p className="text-sm text-muted-foreground mt-4 mb-5 whitespace-pre-wrap" translate="no">{msg.texto}</p></div><div className="pt-4 border-t border-border text-xs"><strong translate="no">{msg.autor}</strong><p className="text-muted-foreground mt-1">{fechaLegible(msg.fecha)}</p></div></article>)}
        {activos.map(item => <article key={item.id_activo} className={claseTarjeta} style={{ borderTopColor: colores[filtro], overflowWrap: 'anywhere' }}><div><div className="flex flex-wrap justify-between gap-2 mb-4"><span className="badge-neutral">{item.formato}</span><span className="badge-neutral">{filtro === 'pendientes' ? 'Pendiente' : 'Aprobado'}</span></div><h3 className="font-bold mb-3" translate="no">{item.titulo}</h3><p className="text-sm text-muted-foreground whitespace-pre-wrap" translate="no">{item.copy}</p></div></article>)}
        {alertas.map(alerta => <article key={alerta.id_alerta} className={claseTarjeta} style={{ borderTopColor: colores.alertas, overflowWrap: 'anywhere' }}><div><span className="badge-neutral">Alerta interna</span><p className="text-sm text-muted-foreground mt-4 whitespace-pre-wrap" translate="no">{alerta.texto}</p><p className="text-sm mt-3"><strong>Motivo:</strong> <span translate="no">{alerta.motivo}</span></p>{alerta.veces > 1 && <p className="text-xs mt-2">Detectada {alerta.veces} veces</p>}</div><div className="pt-4 mt-5 border-t border-border text-xs"><strong translate="no">{/^\d{16,22}$/.test(alerta.autor) ? 'Integrante de Discord' : alerta.autor}</strong><p className="text-muted-foreground mt-1">{fechaLegible(alerta.fecha)}</p><p className="text-muted-foreground mt-2"><strong>Lote:</strong> <span translate="no">{[alerta.origen, alerta.periodo].filter(Boolean).join(' · ') || alerta.trabajo || 'Sin lote identificado'}</span></p><VerMensaje texto={alerta.texto} autor={alerta.autor} canal={alerta.canal} idMensaje={alerta.id_mensaje} /></div></article>)}
      </div>
      {paginas > 1 && <nav aria-label="Páginas de resultados" className="flex flex-wrap justify-end items-center gap-3 mt-5"><button type="button" className="btn-secondary" aria-label="Página anterior" disabled={pagina === 1 || cargando} onClick={() => irAPagina(pagina - 1)}><ChevronLeft size={16}/></button><span className="text-sm">Página {pagina} de {paginas}</span><button type="button" className="btn-secondary" aria-label="Página siguiente" disabled={pagina >= paginas || cargando} onClick={() => irAPagina(pagina + 1)}><ChevronRight size={16}/></button></nav>}
    </>}
  </section></UiTree>;
}
