'use client';


import UiTree from '@/components/UiTree';
import { translateCurrent } from '@/i18n/translate';
import { Suspense, useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  MessageSquare, Edit3, CheckCircle2, XCircle, BookOpen,
  Layers, Loader2, Save, FileText, ChevronLeft, ChevronRight, X, AlertTriangle, ArrowLeft,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { listarActivos, listarLogrosCuraduria, generarPostsLogro, esLogroAcademicoElegible, obtenerDetalleActivo, actualizarActivo, describirError, Activo, EstadoActivo } from '@/services/api';
import Sidebar from '@/components/Sidebar';
import TablaDenegados from '@/components/TablaDenegados';
import { canalLegible } from '@/services/formato';
import { esReferenciaPublicada } from '@/services/referenciaPublicada';
import PanelBanner from '@/components/PanelBanner';
import EstadoOCI from '@/components/EstadoOCI';
import BotonesRedes from '@/components/BotonesRedes';
import RutaProtegida from '@/components/RutaProtegida';

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Etiquetas de los controles de fidelidad (pipelines/communitylab/generadores/fidelidad.py).
const ETIQUETA_ADVERTENCIA: Record<string, string> = {
  cifra_no_sustentada: 'Cifra que no aparece en las fuentes',
  detalle_no_sustentado: 'Detalle no mencionado en las fuentes',
  archivo_no_sustentado: 'Archivo no mencionado en las fuentes',
  diagnostico_no_sustentado: 'Afirma una causa que las fuentes no plantean',
  posible_atribucion_individual: 'Logro colectivo presentado como individual',
};

const ETIQUETA_ESTADO: Record<string, string> = { generado: 'Pendiente', revisado: 'Pendiente', rechazado: 'Denegado', aprobado: 'Aprobado' };
const FILTROS_HISTORIAL = [
  { valor: 'pendientes', etiqueta: 'Pendientes' },
  { valor: 'rechazado', etiqueta: 'Denegados' },
  { valor: 'aprobado', etiqueta: 'Aprobados' },
];

const estadoBadge = (estado: string) => {
  switch (estado) {
    case 'aprobado': return 'badge-success';
    case 'revisado': return 'badge-info';
    case 'rechazado': return 'badge-danger';
    default: return 'badge-warning';
  }
};

// useSearchParams requiere un límite Suspense para no bloquear el prerender (docs de Next 16).
export default function Page() {
  return <UiTree>{(
    <Suspense fallback={null}>
      <CuraduriaPage />
    </Suspense>
  )}</UiTree>;
}

function CuraduriaPage() {
  const parametros = useSearchParams();
  const soloReferencia = esReferenciaPublicada();
  const [activos, setActivos] = useState<Activo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedActivo, setSelectedActivo] = useState<Activo | null>(null);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filtroEstado, setFiltroEstado] = useState<string>(() => ['rechazado', 'aprobado'].includes(parametros.get('estado') ?? '') ? parametros.get('estado')! : 'pendientes');
  const [errorLista, setErrorLista] = useState('');
  const [revisionHistorial, setRevisionHistorial] = useState(0);

  const [loadingList, setLoadingList] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  useEffect(() => {
    if (!drawerOpen) return;
    const alTeclear = (evento: KeyboardEvent) => { if (evento.key === 'Escape') setDrawerOpen(false); };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [drawerOpen]);
  // Móvil: se alterna entre listado y detalle; en escritorio se ven ambos.
  const [vistaMovil, setVistaMovil] = useState<'lista' | 'detalle'>('lista');
  // Filtro opcional por trabajo, desde el enlace "Ver resultados" de la ingesta.
  const [trabajo, setTrabajo] = useState<string | null>(() => parametros.get('trabajo'));

  const [editCopy, setEditCopy] = useState('');
  const [postX, setPostX] = useState('');
  const [generandoPosts, setGenerandoPosts] = useState(false);
  const [errorPosts, setErrorPosts] = useState('');
  const generandoRef = useRef(false);
  const activoVigente = useRef<string | null>(null);
  useEffect(() => { activoVigente.current = selectedId; }, [selectedId]);
  const [comentario, setComentario] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [tieneConsentimiento, setTieneConsentimiento] = useState(false);

  useEffect(() => {
    const abrirPendientes = () => { setFiltroEstado('pendientes'); setPage(1); setTrabajo(null); setVistaMovil('lista'); setDrawerOpen(false); setLoadingList(true); setRevisionHistorial(v => v + 1); };
    window.addEventListener('communitylab-curaduria-pendientes', abrirPendientes);
    return () => window.removeEventListener('communitylab-curaduria-pendientes', abrirPendientes);
  }, []);

  useEffect(() => {
    let vigente = true;
    const cargar = async () => {
      try {
        const res = filtroEstado === 'rechazado'
          ? await listarActivos(page, 10, 'rechazado', trabajo)
          : await listarLogrosCuraduria(page, 10, filtroEstado, trabajo);
        let items = res.items;
        if (filtroEstado === 'rechazado') {
          const detalles = await Promise.allSettled(items.map(a => obtenerDetalleActivo(a.id_activo)));
          items = items.map((item, i) => detalles[i].status === 'fulfilled' ? detalles[i].value : item);
        }
        if (!vigente) return;
        setErrorLista(''); setActivos(items); setTotalPages(res.total_pages || 1);
        setSelectedId(actual => filtroEstado === 'rechazado' ? null : items.some(a => a.id_activo === actual) ? actual : items[0]?.id_activo ?? null);
      } catch { if (vigente) { setActivos([]); setSelectedId(null); setErrorLista('No se pudo cargar el historial de curaduría.'); } }
      finally { if (vigente) setLoadingList(false); }
    };
    void cargar();
    return () => { vigente = false; };
  }, [page, filtroEstado, trabajo, revisionHistorial]);

  useEffect(() => {
    if (!selectedId) return;
    let vigente = true;
    const fetchDetalle = async () => {
      try {
        const res = await obtenerDetalleActivo(selectedId);
        if (!vigente) return;
        if (!esLogroAcademicoElegible(res)) { setSelectedActivo(null); return; }
        setSelectedActivo(res);
        setEditCopy(res.posts_redes?.linkedin ?? res.copy);
        setPostX(res.posts_redes?.x ?? '');
        setErrorPosts('');
        setComentario(res.comentario_curador || '');
        setTieneConsentimiento(false);
        setIsDirty(false);
      } catch (error) {
        console.error('Error al cargar el detalle:', error);
      }
    };
    fetchDetalle();
    return () => { vigente = false; };
  }, [selectedId]);

  const handleUpdate = async (nuevoEstado?: EstadoActivo) => {
    if (!selectedId || selectedActivo?.id_activo !== selectedId || !esLogroAcademicoElegible(selectedActivo) || generandoRef.current) return;

    const pendientes = selectedActivo?.advertencias_fidelidad?.length ?? 0;
    if (nuevoEstado === 'aprobado' && pendientes > 0 && !window.confirm(
      translateCurrent(`Este contenido tiene ${pendientes} advertencia(s) de fidelidad. ¿Confirmas que revisaste el texto frente a las fuentes?`),
    )) {
      return;
    }

    if (nuevoEstado === 'aprobado' && tieneConsentimiento) {
      if (!editCopy.toLowerCase().includes('aprobación de demostración')) {
        alert(translateCurrent('Política ética: Como tienes consentimiento, debes incluir la frase «aprobación de demostración» dentro del texto.'));
        return;
      }
    }

    // El motivo queda en el historial y se muestra en Denegados: se pide si las notas están vacías.
    let notas = comentario;
    if (nuevoEstado === 'rechazado' && !notas.trim()) {
      const motivo = window.prompt(translateCurrent('¿Por qué se deniega este contenido? El motivo se mostrará en Denegados.'));
      if (motivo === null) return;
      if (!motivo.trim()) { alert(translateCurrent('Escribe el motivo de la denegación.')); return; }
      notas = motivo.trim();
      setComentario(notas);
    }

    setSaving(true);
    try {
      const payload: { copy?: string; estado?: EstadoActivo; comentario_curador?: string; posts_redes?: { linkedin: string; x: string } } = {};
      if (isDirty) { payload.copy = editCopy; payload.posts_redes = { linkedin: editCopy, x: postX }; }
      if (notas !== (selectedActivo?.comentario_curador || '')) payload.comentario_curador = notas;
      if (nuevoEstado) payload.estado = nuevoEstado;

      const res = await actualizarActivo(selectedId, payload);
      setSelectedActivo(prev => prev ? { ...prev, ...res } : null);
      setActivos(prev => prev.map(a => a.id_activo === selectedId ? { ...a, ...res } : a));
      setIsDirty(false);
      if (nuevoEstado) {
        setLoadingList(true); setRevisionHistorial(actual => actual + 1);
        window.dispatchEvent(new Event('communitylab-curaduria-cambio'));   // la campanita se actualiza al momento
      }
    } catch (error: unknown) {
      const legible = describirError(error);
      alert(translateCurrent(legible.tipo === 'acceso' ? `${legible.titulo}: ${legible.mensaje}` : legible.mensaje || 'Error guardando los cambios.'));
    } finally {
      setSaving(false);
    }
  };

  const generarPosts = async () => {
    if (!selectedActivo || !esLogroAcademicoElegible(selectedActivo) || soloReferencia || generandoRef.current) return;
    if (isDirty && !window.confirm(translateCurrent('La generación reemplazará los textos sin guardar. ¿Deseas continuar?'))) return;
    const id = selectedActivo.id_activo;
    generandoRef.current = true; setGenerandoPosts(true); setErrorPosts('');
    try {
      const textos = await generarPostsLogro(id);
      if (activoVigente.current !== id) return;
      setEditCopy(textos.linkedin); setPostX(textos.x); setIsDirty(true);
    } catch (error) { if (activoVigente.current === id) setErrorPosts(describirError(error).mensaje); }
    finally { generandoRef.current = false; setGenerandoPosts(false); }
  };

  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full md:overflow-hidden relative">
        <Sidebar />

        {/* Panel izquierdo: lista de borradores (en móvil, solo en la vista de listado) */}
        <div className={`${vistaMovil === 'lista' ? 'flex' : 'hidden'} md:flex w-full md:w-80 shrink-0 flex-col ${filtroEstado === 'rechazado' ? '' : 'min-h-[60dvh]'} md:h-[calc(100dvh-var(--topbar-h))] bg-surface border-r border-border`}>
          <div className="p-5 border-b border-border">
            <h2 className="text-lg font-bold flex items-center gap-2 text-foreground">
              <Layers className="w-5 h-5 text-primary" /> Curaduría
            </h2>
            <p className="text-xs text-muted-foreground mt-2">Logros de la comunidad y contenidos para revisión.</p>
            {trabajo && (
              <p className="mt-3 badge-info max-w-full">
                <span className="truncate">Trabajo {trabajo.slice(0, 8)}…</span>
                <button
                  onClick={() => { setTrabajo(null); setPage(1); setLoadingList(true); window.history.replaceState(null, '', '/curaduria'); }}
                  className="underline underline-offset-2 shrink-0"
                >
                  Quitar filtro
                </button>
              </p>
            )}
            <h3 className="text-xs font-bold text-foreground mt-4 mb-2">Historial de curaduría</h3>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar historial por estado">
              {FILTROS_HISTORIAL.map(({ valor: st, etiqueta }) => (
                <button
                  key={st}
                  onClick={() => { setFiltroEstado(st); setPage(1); setLoadingList(true); setVistaMovil('lista'); setDrawerOpen(false); }}
                  aria-pressed={filtroEstado === st}
                  className="filtro-borrador"
                >
                  {etiqueta}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {filtroEstado === 'rechazado' ? <p className="p-5 text-sm text-muted-foreground">Las denegaciones se muestran en la tabla, con su mensaje y motivo.</p> : errorLista ? <p role="alert" className="p-5 text-sm">{errorLista}</p> : loadingList ? (
              <div className="p-8 text-center text-subtle-foreground">
                <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
              </div>
            ) : activos.length === 0 ? (
              <p className="p-8 text-center text-sm text-subtle-foreground">No hay logros académicos verificados en este estado.</p>
            ) : activos.map(a => (
              <button type="button"
                key={a.id_activo}
                onClick={() => { setSelectedId(a.id_activo); setVistaMovil('detalle'); }}
                className={`w-full text-left px-4 py-3.5 cursor-pointer border-b border-border border-l-2 transition-colors ${
                  selectedId === a.id_activo
                    ? 'bg-primary-soft border-l-primary'
                    : 'border-l-transparent hover:bg-surface-hover'
                }`}
              >
                <div className="flex justify-between items-center mb-1.5 gap-2">
                  <span className="badge-violet">{a.formato}</span>
                  <span className="flex items-center gap-1.5">
                    {!!a.advertencias_fidelidad?.length && (
                      <span className="badge-warning" title="Advertencias de fidelidad">
                        <AlertTriangle className="w-3 h-3" /> {a.advertencias_fidelidad.length}
                      </span>
                    )}
                    <span className={estadoBadge(a.estado)}>{ETIQUETA_ESTADO[a.estado] ?? a.estado}</span>
                    {a.estado === 'aprobado' && <EstadoOCI registro={a.almacenamiento_oci} />}
                  </span>
                </div>
                <h3 className="text-sm font-medium text-foreground truncate" translate="no">{a.titulo}</h3>
                <p className="text-xs text-muted-foreground mt-1" translate={(a.fuentes?.length ?? 0) > 1 ? 'yes' : 'no'}>{(a.fuentes?.length ?? 0) > 1 ? `${a.fuentes.length} fuentes` : a.autor_fuente ? a.autor_fuente : a.fuentes_detalle?.[0]?.autor && !/^\d{16,22}$/.test(a.fuentes_detalle[0].autor) ? a.fuentes_detalle[0].autor : 'Autor no disponible'}</p><p className="text-xs text-muted-foreground line-clamp-2 mt-1" translate="no">{a.copy}</p>
                <p className="text-xs text-muted-foreground mt-1">{new Date(a.fecha_actualizacion).toLocaleString('es')}</p>
              </button>
            ))}
          </div>

          <div className="px-4 py-3 border-t border-border flex items-center justify-between">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary px-2.5! py-2!"
              aria-label="Página anterior"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-subtle-foreground tabular-nums">Página {page} de {totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="btn-secondary px-2.5! py-2!"
              aria-label="Página siguiente"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Editor principal (en móvil, solo en la vista de detalle) */}
        <div className={`${vistaMovil === 'detalle' || filtroEstado === 'rechazado' ? 'flex' : 'hidden'} md:flex flex-1 min-w-0 min-h-0 flex-col md:h-[calc(100dvh-var(--topbar-h))] relative`}>
          {filtroEstado === 'rechazado' ? <div className="flex-1 min-h-0 overflow-y-auto"><TablaDenegados activos={activos} cargando={loadingList} error={errorLista} reintentar={() => { setLoadingList(true); setRevisionHistorial(v => v + 1); }} /></div> : selectedActivo && selectedActivo.id_activo === selectedId ? (
            <>
              <div className="px-4 sm:px-6 py-4 sm:py-5 border-b border-border bg-surface flex flex-wrap justify-between items-center gap-3">
                <button onClick={() => setVistaMovil('lista')} className="btn-ghost px-2! py-2! md:hidden" aria-label="Volver al listado">
                  <ArrowLeft className="w-4 h-4" /> Listado
                </button>
                <div className="min-w-0 flex-1 basis-full order-last md:order-none md:basis-0">
                  <h1 className="text-xl font-bold text-foreground mb-1 truncate" translate="no">{selectedActivo.titulo}</h1>
                  <p className="text-xs text-muted-foreground">
                    Versión {selectedActivo.version} · Actualizado {new Date(selectedActivo.fecha_actualizacion).toLocaleString()}
                  </p>
                  {selectedActivo.estado === 'aprobado' && selectedActivo.almacenamiento_oci && <div className="mt-2"><EstadoOCI registro={selectedActivo.almacenamiento_oci} conDetalle /></div>}
                </div>
                <button onClick={() => setDrawerOpen(true)} className="btn-secondary shrink-0">
                  <BookOpen className="w-4 h-4 text-info" />
                  Ver fuentes ({selectedActivo.fuentes_detalle?.length || selectedActivo.fuentes.length})
                </button>
              </div>

              <div className="flex-1 min-h-0 min-w-0 p-4 sm:p-6 flex flex-col gap-4 md:overflow-y-auto [&>*]:shrink-0">
                {!!selectedActivo.advertencias_fidelidad?.length && (
                  <div className="rounded-xl border border-warning/30 bg-warning-soft p-4 text-sm">
                    <p className="font-semibold text-warning flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" /> Revisar fidelidad frente a las fuentes
                    </p>
                    <ul className="mt-2 space-y-1 text-foreground">
                      {selectedActivo.advertencias_fidelidad.map((adv, i) => (
                        <li key={i}>{ETIQUETA_ADVERTENCIA[adv.tipo] ?? adv.tipo}: <span className="font-mono">{adv.detalle}</span></li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Controles automáticos: no detectan toda afirmación inventada. Contrasta el texto con «Ver fuentes».
                    </p>
                  </div>
                )}
                <div className="card flex flex-col min-w-0 shrink-0 p-5">
                  <div className="flex flex-wrap justify-between items-center gap-3 mb-3">
                    <label className="text-xs font-semibold text-subtle-foreground uppercase tracking-wider">
                      Cuerpo del contenido
                    </label>
                    <button type="button" className="btn-secondary" disabled={soloReferencia || generandoPosts || saving || !esLogroAcademicoElegible(selectedActivo)} onClick={generarPosts}>{generandoPosts ? <Loader2 className="w-4 h-4 animate-spin"/> : <FileText className="w-4 h-4"/>}Generar post</button>
                    {isDirty && <span className="badge-warning">Cambios sin guardar</span>}
                  </div>
                  <BotonesRedes textoLinkedin={editCopy} textoX={postX} />
                  {errorPosts && <p role="alert" className="text-sm text-danger mb-3">{errorPosts}</p>}
                  <p className="text-xs font-bold mb-2">Texto para LinkedIn</p>
                  <textarea
                    aria-label="Texto para LinkedIn"
                    readOnly={soloReferencia || generandoPosts}
                    value={editCopy}
                    onChange={(e) => { setEditCopy(e.target.value); setIsDirty(true); }}
                    className="input min-h-40 resize-y"
                    placeholder="Redacta el contenido…"
                  />
                  <p className="text-xs font-bold mt-4 mb-2">Texto para X</p>
                  <textarea aria-label="Texto para X" readOnly={soloReferencia || generandoPosts} value={postX} onChange={e => { setPostX(e.target.value); setIsDirty(true); }} className="input min-h-28 resize-y" placeholder="Texto de la publicación para X…" />

                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="card p-5 flex flex-col justify-between gap-4">
                    <div>
                      <label className="text-xs font-semibold text-foreground mb-2 block uppercase tracking-wider">
                        Control de consentimiento
                      </label>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        ¿El usuario autorizó el uso de su identidad en esta publicación?
                      </p>
                    </div>

                    <div className="flex flex-col gap-3">
                      <label className="flex items-center gap-3 cursor-pointer w-fit">
                        <input
                          type="checkbox"
                          disabled={soloReferencia}
                          checked={tieneConsentimiento}
                          onChange={(e) => setTieneConsentimiento(e.target.checked)}
                          className="w-4 h-4 accent-primary"
                        />
                        <span className="text-sm font-medium text-foreground">Sí, cuenta con consentimiento verificable</span>
                      </label>

                      {!tieneConsentimiento && (
                        <button
                          disabled={soloReferencia}
                          onClick={() => {
                            const autorOriginal = selectedActivo?.fuentes_detalle?.[0]?.autor;
                            if (!autorOriginal) return;
                            setEditCopy(prev => prev.replace(new RegExp(escapeRegExp(autorOriginal), 'g'), 'Un miembro de la comunidad'));
                            setIsDirty(true);
                          }}
                          className="text-xs font-medium text-warning bg-warning-soft hover:brightness-95 border border-warning/25 py-2 px-3 rounded-lg w-full transition text-left"
                        >
                          Aplicar autor ficticio por falta de permiso
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="card p-5">
                    <label className="text-xs font-semibold text-subtle-foreground mb-2 block uppercase tracking-wider">
                      Notas del curador
                    </label>
                    <textarea
                      readOnly={soloReferencia}
                      value={comentario}
                      onChange={(e) => { setComentario(e.target.value); setIsDirty(true); }}
                      placeholder="Justificación del ajuste…"
                      className="input h-24 resize-none"
                    />
                  </div>
                </div>

                <section className="card p-5" aria-labelledby="historial-contenido">
                  <h2 id="historial-contenido" className="text-sm font-bold mb-3">Historial del contenido</h2>
                  {selectedActivo.historial?.length ? <ol className="space-y-3">{selectedActivo.historial.map((evento, indice) => <li key={indice} className="border-l-2 border-border pl-3"><div className="flex flex-wrap gap-2 items-center"><span className={estadoBadge(evento.estado)}>{ETIQUETA_ESTADO[evento.estado] ?? evento.estado}</span><time className="text-xs text-muted-foreground" dateTime={evento.fecha}>{new Date(evento.fecha).toLocaleString('es')}</time></div>{evento.comentario && <p className="text-xs text-muted-foreground mt-1" translate="no">{evento.comentario}</p>}</li>)}</ol> : <p className="text-xs text-muted-foreground">Estado actual: {ETIQUETA_ESTADO[selectedActivo.estado] ?? selectedActivo.estado}. El historial de cambios aún no está disponible.</p>}
                </section>

                {soloReferencia ? <section className="card p-5"><h2 className="text-sm font-semibold">Banner del contenido</h2><p className="text-xs text-muted-foreground mt-2">Aprueba el texto para generar el banner. La aprobación del banner no lo publica. Esta muestra local es de solo lectura y no incluye los archivos de imagen.</p></section> : <PanelBanner
                  idActivo={selectedActivo.id_activo}
                  estadoActivo={selectedActivo.estado}
                  version={selectedActivo.version}
                />}
              </div>

              {/* Barra de acciones */}
              <div className="px-4 sm:px-6 py-4 border-t border-border bg-surface flex justify-between items-center shrink-0 gap-3 flex-wrap">
                <div className="flex flex-wrap items-center gap-3">
                  <button disabled={soloReferencia || saving || generandoPosts || !isDirty} onClick={() => handleUpdate()} className="btn-secondary">
                    <Save className="w-4 h-4" /> Guardar texto
                  </button>
                  {/* AQUÍ ESTABA TokenOperador, ya lo quitamos para usar JWT automático */}
                </div>
                <div className="flex gap-2.5 flex-wrap">
                  <button disabled={soloReferencia || saving || selectedActivo.estado === 'rechazado'} onClick={() => handleUpdate('rechazado')} className="btn-danger-soft">
                    <XCircle className="w-4 h-4" /> Denegar
                  </button>
                  <button disabled={soloReferencia || saving || selectedActivo.estado === 'aprobado'} onClick={() => handleUpdate('aprobado')} className="btn-success">
                    <CheckCircle2 className="w-4 h-4" /> Aprobar como definitivo
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-subtle-foreground text-sm">
              <div className="card p-6 w-full max-w-2xl text-left">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><h2 className="font-bold text-foreground">Cuerpo del contenido</h2><button className="btn-secondary" disabled><FileText className="w-4 h-4"/>Generar post</button></div>
                <BotonesRedes />
                <p className="text-sm text-muted-foreground flex gap-2"><Edit3 className="w-4 h-4 shrink-0"/>Selecciona un logro académico verificado para revisar el banner y generar los textos de LinkedIn y X.</p>
              </div>
            </div>
          )}
        </div>

        {/* Drawer de trazabilidad */}
        <AnimatePresence>
          {drawerOpen && (
            <>
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                onClick={() => setDrawerOpen(false)}
                className="absolute inset-0 bg-black/40 z-40"
              />
              <motion.div
                initial={{ x: 450 }} animate={{ x: 0 }} exit={{ x: 450 }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                role="dialog" aria-modal="true" aria-label="Mensajes fuente originales"
                className="absolute right-0 top-0 h-full w-[400px] max-w-full bg-surface border-l border-border z-50 flex flex-col shadow-lg"
              >
                <div className="p-5 border-b border-border flex justify-between items-center">
                  <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-info" /> Mensajes fuente originales
                  </h3>
                  <button onClick={() => setDrawerOpen(false)} className="btn-ghost px-2! py-2!" aria-label="Cerrar">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 p-5 overflow-y-auto flex flex-col gap-3">
                  {selectedActivo?.fuentes_detalle?.map(f => (
                    <div key={f.id_mensaje} className="card p-4">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-semibold text-foreground" translate="no">{f.autor}</span>
                        <span className="badge-neutral">{canalLegible(f.canal)}</span>
                      </div>
                      <p className="text-sm text-muted-foreground italic leading-relaxed" translate="no">&quot;{f.texto}&quot;</p>
                    </div>
                  ))}
                  {(!selectedActivo?.fuentes_detalle || selectedActivo.fuentes_detalle.length === 0) && (
                    <p className="text-xs text-subtle-foreground text-center mt-10">
                      No se encontraron fuentes detalladas para este activo.
                    </p>
                  )}
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </RutaProtegida>
  )}</UiTree>;
}
