'use client';

import axios from 'axios';
import { useState, useEffect } from 'react';
import {
  MessageSquare, Edit3, CheckCircle2, XCircle, Clock, BookOpen,
  Layers, Loader2, Save, ChevronLeft, ChevronRight, X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { listarActivos, obtenerDetalleActivo, actualizarActivo, Activo, EstadoActivo } from '@/services/api';
import Sidebar from '@/components/Sidebar';

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const estadoBadge = (estado: string) => {
  switch (estado) {
    case 'aprobado': return 'badge-success';
    case 'revisado': return 'badge-info';
    case 'rechazado': return 'badge-danger';
    default: return 'badge-warning';
  }
};

export default function CuraduriaPage() {
  const [activos, setActivos] = useState<Activo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedActivo, setSelectedActivo] = useState<Activo | null>(null);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filtroEstado, setFiltroEstado] = useState<string>('');

  const [loadingList, setLoadingList] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const [editCopy, setEditCopy] = useState('');
  const [comentario, setComentario] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [tieneConsentimiento, setTieneConsentimiento] = useState(false);

  useEffect(() => {
    let vigente = true;
    listarActivos(page, 10, filtroEstado).then(res => {
      if (!vigente) return;
      setActivos(res.items);
      setTotalPages(res.total_pages || 1);
      setSelectedId(actual => res.items.some(a => a.id_activo === actual) ? actual : res.items[0]?.id_activo ?? null);
      setLoadingList(false);
    }).catch(error => {
      if (vigente) setLoadingList(false);
      console.error('Error al cargar activos:', error);
    });
    return () => { vigente = false; };
  }, [page, filtroEstado]);

  useEffect(() => {
    if (!selectedId) return;
    let vigente = true;
    const fetchDetalle = async () => {
      try {
        const res = await obtenerDetalleActivo(selectedId);
        if (!vigente) return;
        setSelectedActivo(res);
        setEditCopy(res.copy);
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
    if (!selectedId || selectedActivo?.id_activo !== selectedId) return;

    if (nuevoEstado === 'aprobado' && tieneConsentimiento) {
      if (!editCopy.toLowerCase().includes('aprobación de demostración')) {
        alert('Política Ética: Como tienes consentimiento, debes incluir la frase «aprobación de demostración» dentro del texto.');
        return;
      }
    }

    setSaving(true);
    try {
      const payload: { copy?: string; estado?: EstadoActivo; comentario_curador?: string } = {};
      if (isDirty) payload.copy = editCopy;
      if (comentario !== (selectedActivo?.comentario_curador || '')) payload.comentario_curador = comentario;
      if (nuevoEstado) payload.estado = nuevoEstado;

      const res = await actualizarActivo(selectedId, payload);
      setSelectedActivo(prev => prev ? { ...prev, ...res } : null);
      setActivos(prev => prev.map(a => a.id_activo === selectedId ? { ...a, ...res } : a));
      setIsDirty(false);
    } catch (error: unknown) {
      alert(axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Error guardando los cambios.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full overflow-hidden relative">
      <Sidebar />

      {/* Panel izquierdo: lista de borradores */}
      <div className="w-80 shrink-0 flex flex-col h-screen bg-surface border-r border-border">
        <div className="p-5 border-b border-border">
          <h2 className="text-lg font-bold flex items-center gap-2 text-foreground">
            <Layers className="w-5 h-5 text-primary" /> Borradores
          </h2>
          <div className="flex flex-wrap gap-2 mt-4">
            {['', 'generado', 'revisado', 'aprobado'].map(st => (
              <button
                key={st}
                onClick={() => { setFiltroEstado(st); setPage(1); setLoadingList(true); }}
                className={filtroEstado === st ? 'badge-primary' : 'badge-neutral hover:border-border-strong'}
              >
                {st === '' ? 'Todos' : st.charAt(0).toUpperCase() + st.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loadingList ? (
            <div className="p-8 text-center text-subtle-foreground">
              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
            </div>
          ) : activos.length === 0 ? (
            <p className="p-8 text-center text-sm text-subtle-foreground">Sin borradores en este estado.</p>
          ) : activos.map(a => (
            <div
              key={a.id_activo}
              onClick={() => setSelectedId(a.id_activo)}
              className={`px-4 py-3.5 cursor-pointer border-b border-border border-l-2 transition-colors ${
                selectedId === a.id_activo
                  ? 'bg-primary-soft border-l-primary'
                  : 'border-l-transparent hover:bg-surface-hover'
              }`}
            >
              <div className="flex justify-between items-center mb-1.5">
                <span className="badge-violet">{a.formato}</span>
                <span className={estadoBadge(a.estado)}>{a.estado}</span>
              </div>
              <h3 className="text-sm font-medium text-foreground truncate">{a.titulo}</h3>
              <p className="text-xs text-subtle-foreground truncate mt-0.5 font-mono">{a.id_activo}</p>
            </div>
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
          <span className="text-xs text-subtle-foreground tabular-nums">Pág {page} / {totalPages}</span>
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

      {/* Editor principal */}
      <div className="flex-1 min-w-0 flex flex-col h-screen relative">
        {selectedActivo && selectedActivo.id_activo === selectedId ? (
          <>
            <div className="px-6 py-5 border-b border-border bg-surface flex justify-between items-center gap-4">
              <div className="min-w-0">
                <h1 className="text-xl font-bold text-foreground mb-1 truncate">{selectedActivo.titulo}</h1>
                <p className="text-xs text-muted-foreground">
                  Versión {selectedActivo.version} · Actualizado {new Date(selectedActivo.fecha_actualizacion).toLocaleString()}
                </p>
              </div>
              <button onClick={() => setDrawerOpen(true)} className="btn-secondary shrink-0">
                <BookOpen className="w-4 h-4 text-info" />
                Ver fuentes ({selectedActivo.fuentes_detalle?.length || selectedActivo.fuentes.length})
              </button>
            </div>

            <div className="flex-1 p-6 flex flex-col gap-4 overflow-y-auto">
              <div className="card flex-1 flex flex-col p-5 min-h-[250px]">
                <div className="flex justify-between items-center mb-3">
                  <label className="text-xs font-semibold text-subtle-foreground uppercase tracking-wider">
                    Cuerpo del contenido
                  </label>
                  {isDirty && <span className="badge-warning">Cambios sin guardar</span>}
                </div>
                <textarea
                  value={editCopy}
                  onChange={(e) => { setEditCopy(e.target.value); setIsDirty(true); }}
                  className="w-full flex-1 bg-transparent border-none outline-none text-sm text-foreground resize-none font-mono leading-relaxed placeholder:text-subtle-foreground"
                  placeholder="Redacta el contenido..."
                />
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
                        checked={tieneConsentimiento}
                        onChange={(e) => setTieneConsentimiento(e.target.checked)}
                        className="w-4 h-4 accent-primary"
                      />
                      <span className="text-sm font-medium text-foreground">Sí, cuenta con consentimiento verificable</span>
                    </label>

                    {!tieneConsentimiento && (
                      <button
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
                    value={comentario}
                    onChange={(e) => { setComentario(e.target.value); setIsDirty(true); }}
                    placeholder="Justificación del ajuste..."
                    className="input h-24 resize-none"
                  />
                </div>
              </div>
            </div>

            {/* Barra de acciones */}
            <div className="px-6 py-4 border-t border-border bg-surface flex justify-between items-center shrink-0 gap-3 flex-wrap">
              <button disabled={saving || !isDirty} onClick={() => handleUpdate()} className="btn-secondary">
                <Save className="w-4 h-4" /> Guardar texto
              </button>
              <div className="flex gap-2.5 flex-wrap">
                <button disabled={saving || selectedActivo.estado === 'rechazado'} onClick={() => handleUpdate('rechazado')} className="btn-danger-soft">
                  <XCircle className="w-4 h-4" /> Rechazar
                </button>
                <button disabled={saving || selectedActivo.estado === 'revisado'} onClick={() => handleUpdate('revisado')} className="btn-info-soft">
                  <Clock className="w-4 h-4" /> Marcar revisado
                </button>
                <button disabled={saving || selectedActivo.estado === 'aprobado'} onClick={() => handleUpdate('aprobado')} className="btn-success">
                  <CheckCircle2 className="w-4 h-4" /> Aprobar definitivo
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-subtle-foreground text-sm">
            <span className="inline-flex items-center gap-2"><Edit3 className="w-4 h-4" /> Selecciona un borrador del panel lateral para comenzar.</span>
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
                      <span className="text-xs font-semibold text-foreground">{f.autor}</span>
                      <span className="badge-neutral">{f.canal}</span>
                    </div>
                    <p className="text-sm text-muted-foreground italic leading-relaxed">&quot;{f.texto}&quot;</p>
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
  );
}