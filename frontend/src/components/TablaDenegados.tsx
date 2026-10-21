import type { Activo } from '@/services/api';
import { Loader2 } from 'lucide-react';
// Un resumen puede citar decenas de mensajes: la tabla muestra los primeros para seguir siendo legible.
const FUENTES_VISIBLES = 3;
export default function TablaDenegados({ activos, cargando, error, reintentar }: { activos: Activo[]; cargando: boolean; error: string; reintentar: () => void }) {
  return <section className="p-4 sm:p-6 min-w-0" aria-labelledby="titulo-denegados" aria-busy={cargando}>
    <h1 id="titulo-denegados" className="text-2xl font-bold">Mensajes denegados</h1>
    <p className="text-sm text-muted-foreground mt-2 mb-6">Consulta el mensaje y el motivo de cada denegación.</p>
    {cargando ? <div className="card p-8"><Loader2 className="animate-spin mx-auto" aria-label="Cargando denegaciones" /></div> : error ? <div role="alert" className="card p-6"><p>{error}</p><button className="btn-secondary mt-3" onClick={reintentar}>Reintentar</button></div> : !activos.length ? <p className="card p-6 text-muted-foreground">No hay mensajes denegados.</p> : <div className="card denied-table-card"><table className="denied-table"><caption className="sr-only">Historial de mensajes denegados</caption><thead><tr><th>Nombre</th><th>Logro o contenido y mensaje</th><th>Motivo de denegación</th><th>Fecha</th></tr></thead><tbody>{activos.map(activo => {
      const evento = [...(activo.historial ?? [])].reverse().find(e => e.estado === 'rechazado');
      const autor = activo.fuentes_detalle?.[0]?.autor;
      return <tr key={activo.id_activo}><td data-label="Nombre" translate="no">{autor && !/^\d{16,22}$/.test(autor) ? autor : autor ? 'Integrante de Discord' : 'Nombre no disponible'}</td><td data-label="Logro o contenido y mensaje"><strong translate="no">{activo.titulo || 'Logro no especificado'}</strong><p className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap" translate="no">{activo.fuentes_detalle?.slice(0, FUENTES_VISIBLES).map(f => f.texto).join('\n\n') || activo.copy || 'Mensaje no disponible'}</p>{(activo.fuentes_detalle?.length ?? 0) > FUENTES_VISIBLES && <p className="mt-2 text-xs text-subtle-foreground">y {(activo.fuentes_detalle?.length ?? 0) - FUENTES_VISIBLES} mensaje(s) más en las fuentes</p>}</td><td data-label="Motivo de denegación" translate="no">{evento?.comentario || activo.comentario_curador || 'Motivo no disponible'}</td><td data-label="Fecha">{new Date(evento?.fecha || activo.fecha_actualizacion).toLocaleDateString('es')}</td></tr>;
    })}</tbody></table></div>}
  </section>;
}
