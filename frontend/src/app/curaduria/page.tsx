'use client';

import Link from 'next/link';
import { useState, useEffect, useCallback } from 'react';
import { 
  Database, LayoutDashboard, MessageSquare, UploadCloud, Edit3, 
  CheckCircle2, XCircle, Clock, BookOpen, Layers, Loader2, Save 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { listarActivos, obtenerDetalleActivo, actualizarActivo, Activo, EstadoActivo } from '@/services/api';

export default function CuraduriaPage() {
  const [activos, setActivos] = useState<Activo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedActivo, setSelectedActivo] = useState<Activo | null>(null);
  
  // Paginación y filtros
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filtroEstado, setFiltroEstado] = useState<string>('');
  
  // Estados UI
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  
  // Edición y Tarea 2: Consentimiento Ético
  const [editCopy, setEditCopy] = useState('');
  const [comentario, setComentario] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [tieneConsentimiento, setTieneConsentimiento] = useState(false);

  // 1. Cargar la lista lateral
  const fetchLista = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await listarActivos(page, 10, filtroEstado);
      setActivos(res.items);
      setTotalPages(res.total_pages);
      
      if (res.items.length > 0 && !selectedId) {
        setSelectedId(res.items[0].id_activo);
      }
    } catch (error) {
      console.error("Error al cargar la lista de activos:", error);
    } finally {
      setLoadingList(false);
    }
  }, [page, filtroEstado, selectedId]);

  useEffect(() => {
    fetchLista();
  }, [fetchLista]);

  // 2. Cargar el detalle al seleccionar un activo
  useEffect(() => {
    if (!selectedId) return;
    
    const fetchDetalle = async () => {
      setLoadingDetail(true);
      try {
        const res = await obtenerDetalleActivo(selectedId);
        setSelectedActivo(res);
        setEditCopy(res.copy);
        setComentario(res.comentario_curador || '');
        setTieneConsentimiento(false); // Resetea el switch al cambiar de activo
        setIsDirty(false);
      } catch (error) {
        console.error("Error al cargar el detalle:", error);
      } finally {
        setLoadingDetail(false);
      }
    };
    fetchDetalle();
  }, [selectedId]);

  // 3. Guardar cambios
  const handleUpdate = async (nuevoEstado?: EstadoActivo) => {
    if (!selectedId) return;

    // Validación ética para la Aprobación
    if (nuevoEstado === 'aprobado' && tieneConsentimiento) {
      if (!editCopy.toLowerCase().includes("aprobación de demostración")) {
        alert("Política Ética: Como tienes consentimiento, debes incluir la frase «aprobación de demostración» dentro del texto.");
        return;
      }
    }

    setSaving(true);
    
    try {
      const payload: any = {};
      if (isDirty) payload.copy = editCopy;
      if (comentario !== (selectedActivo?.comentario_curador || '')) payload.comentario_curador = comentario;
      if (nuevoEstado) payload.estado = nuevoEstado;

      const res = await actualizarActivo(selectedId, payload);
      
      // Refrescar UI localmente
      setSelectedActivo((prev) => prev ? { ...prev, ...res } : null);
      setActivos((prev) => prev.map(a => a.id_activo === selectedId ? { ...a, ...res } : a));
      setIsDirty(false);
    } catch (error: any) {
      alert(error.response?.data?.detail || "Error guardando los cambios.");
    } finally {
      setSaving(false);
    }
  };

  const badgeColor = (estado: string) => {
    switch(estado) {
      case 'aprobado': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'revisado': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'rechazado': return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      default: return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0714] flex text-slate-200 selection:bg-blue-500/30 overflow-hidden font-sans relative">
      <div className="absolute top-1/4 right-1/4 w-[450px] h-[450px] bg-blue-600/10 rounded-full blur-[130px] pointer-events-none" />
      
      {/* Sidebar (Idéntico a tus otras pantallas) */}
      <aside className="w-60 border-r border-white/10 bg-white/[0.02] backdrop-blur-xl p-5 flex-col gap-8 hidden md:flex z-10 shrink-0">
        <div className="flex items-center gap-2.5 px-2 pt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-[0_0_20px_rgba(59,130,246,0.5)]">
            <Database className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-[15px] bg-gradient-to-r from-indigo-300 to-blue-300 bg-clip-text text-transparent">
            CommunityLab
          </span>
        </div>
        <nav className="flex flex-col gap-1.5">
          <Link href="/" className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium">
            <LayoutDashboard className="w-4 h-4" /> Dashboard
          </Link>
          <Link href="/ingesta" className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium">
            <UploadCloud className="w-4 h-4" /> Ingesta
          </Link>
          <Link href="/interacciones" className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium">
            <MessageSquare className="w-4 h-4" /> Interacciones
          </Link>
          <Link href="/curaduria" className="flex items-center gap-3 text-white bg-gradient-to-r from-indigo-500/20 to-blue-500/10 border border-blue-500/30 px-3 py-2.5 rounded-xl text-sm font-medium shadow-[0_0_20px_rgba(59,130,246,0.15)]">
            <Edit3 className="w-4 h-4 text-blue-300" /> Curaduría
          </Link>
        </nav>
      </aside>

      {/* Panel Izquierdo: Lista de Borradores */}
      <div className="w-80 border-r border-white/10 bg-white/[0.02] flex flex-col h-screen z-10 shrink-0">
        <div className="p-5 border-b border-white/10">
          <h2 className="text-lg font-bold flex items-center gap-2 text-white">
            <Layers className="w-5 h-5 text-indigo-400" /> Borradores
          </h2>
          <div className="flex flex-wrap gap-2 mt-4 pb-1">
            {['', 'generado', 'revisado', 'aprobado'].map(st => (
              <button 
                key={st} onClick={() => { setFiltroEstado(st); setPage(1); }}
                className={`text-[11px] px-3 py-1 rounded-full border transition-all whitespace-nowrap ${filtroEstado === st ? 'bg-indigo-600/30 border-indigo-500 text-white' : 'bg-white/5 border-white/10 text-slate-400 hover:text-white'}`}
              >
                {st === '' ? 'Todos' : st.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-white/5">
          {loadingList ? (
             <div className="p-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></div>
          ) : activos.map(a => (
            <div 
              key={a.id_activo} onClick={() => setSelectedId(a.id_activo)}
              className={`p-4 cursor-pointer transition-colors ${selectedId === a.id_activo ? 'bg-blue-500/10 border-l-2 border-blue-400' : 'hover:bg-white/[0.03]'}`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="text-[10px] font-bold text-indigo-300 uppercase">{a.formato}</span>
                <span className={`text-[9px] px-2 py-0.5 rounded border font-medium ${badgeColor(a.estado)}`}>{a.estado.toUpperCase()}</span>
              </div>
              <h3 className="text-sm font-medium text-slate-200 truncate">{a.titulo}</h3>
              <p className="text-xs text-slate-500 truncate mt-1">{a.id_activo}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Editor Principal */}
      <div className="flex-1 flex flex-col h-screen bg-transparent z-10 relative">
        {selectedActivo ? (
          <>
            {/* Header Editor */}
            <div className="p-6 border-b border-white/10 flex justify-between items-center backdrop-blur-sm bg-black/20">
              <div>
                <h1 className="text-xl font-bold text-white mb-1">{selectedActivo.titulo}</h1>
                <p className="text-xs text-slate-400">Versión: {selectedActivo.version} · Última actualización: {new Date(selectedActivo.fecha_actualizacion).toLocaleString()}</p>
              </div>
              <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 text-xs bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl transition-all">
                <BookOpen className="w-4 h-4 text-blue-400" />
                Ver Fuentes ({selectedActivo.fuentes_detalle?.length || selectedActivo.fuentes.length})
              </button>
            </div>

            {/* Zona de texto principal */}
            <div className="flex-1 p-6 flex flex-col gap-4 overflow-y-auto">
              <div className="flex-1 flex flex-col bg-white/[0.03] backdrop-blur-xl rounded-2xl border border-white/10 p-5 min-h-[250px]">
                <div className="flex justify-between items-center mb-3">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Cuerpo del Contenido</label>
                  {isDirty && <span className="text-xs text-amber-400 font-medium">Cambios sin guardar...</span>}
                </div>
                <textarea
                  value={editCopy}
                  onChange={(e) => { setEditCopy(e.target.value); setIsDirty(true); }}
                  className="w-full flex-1 bg-transparent border-none focus:ring-0 text-sm text-slate-200 resize-none font-mono leading-relaxed"
                  placeholder="Redacta el contenido..."
                />
              </div>

              {/* Tarea 2: Controles Éticos y Notas */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white/[0.03] backdrop-blur-xl rounded-2xl border border-white/10 p-5 flex flex-col justify-between">
                  <div>
                    <label className="text-xs font-semibold text-indigo-300 mb-2 block uppercase tracking-wider">Control de Consentimiento</label>
                    <p className="text-xs text-slate-400 leading-relaxed mb-4">¿El usuario autorizó el uso de su identidad en esta publicación?</p>
                  </div>
                  
                  <div className="flex flex-col gap-3">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={tieneConsentimiento}
                        onChange={(e) => {
                          setTieneConsentimiento(e.target.checked);
                          setIsDirty(true);
                        }}
                        className="w-4 h-4 rounded border-white/20 bg-black/20 text-indigo-500 focus:ring-indigo-500/50 focus:ring-offset-0" 
                      />
                      <span className="text-sm font-medium text-slate-200">Sí, cuenta con consentimiento verificable</span>
                    </label>

                    {!tieneConsentimiento && (
                      <button 
                        onClick={() => {
                          const autorOriginal = selectedActivo?.fuentes_detalle?.[0]?.autor || 'Autor';
                          setEditCopy(prev => prev.replace(new RegExp(autorOriginal, 'g'), 'Un miembro de la comunidad'));
                          setIsDirty(true);
                        }}
                        className="text-xs text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 py-2 px-3 rounded-lg w-full transition-colors font-medium text-left"
                      >
                        Aplicar autor ficticio por falta de permiso
                      </button>
                    )}
                  </div>
                </div>

                <div className="bg-white/[0.03] backdrop-blur-xl rounded-2xl border border-white/10 p-5">
                  <label className="text-xs font-semibold text-slate-400 mb-2 block uppercase tracking-wider">Notas del Curador</label>
                  <textarea
                    value={comentario} 
                    onChange={(e) => { setComentario(e.target.value); setIsDirty(true); }}
                    placeholder="Justificación del ajuste..."
                    className="w-full h-20 resize-none bg-black/20 border border-white/10 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-400/50 placeholder:text-slate-600"
                  />
                </div>
              </div>
            </div>

            {/* Action Bar (Máquina de Estados) */}
            <div className="p-5 border-t border-white/10 bg-black/40 backdrop-blur-xl flex justify-between items-center shrink-0">
              <button disabled={saving || !isDirty} onClick={() => handleUpdate()} className="flex items-center gap-2 bg-indigo-600/80 hover:bg-indigo-500 text-white text-xs font-medium px-5 py-2.5 rounded-xl disabled:opacity-40 transition-all shadow-lg">
                <Save className="w-4 h-4" /> Guardar Texto
              </button>
              <div className="flex gap-3">
                <button disabled={saving || selectedActivo.estado === 'rechazado'} onClick={() => handleUpdate('rechazado')} className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20 hover:bg-rose-500/20 disabled:opacity-40 transition-all">
                  <XCircle className="w-4 h-4" /> Rechazar
                </button>
                <button disabled={saving || selectedActivo.estado === 'revisado'} onClick={() => handleUpdate('revisado')} className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 disabled:opacity-40 transition-all">
                  <Clock className="w-4 h-4" /> Marcar Revisado
                </button>
                <button disabled={saving || selectedActivo.estado === 'aprobado'} onClick={() => handleUpdate('aprobado')} className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-xs font-semibold bg-emerald-600/80 hover:bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.3)] disabled:opacity-40 transition-all">
                  <CheckCircle2 className="w-4 h-4" /> Aprobar Definitivo
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">Selecciona un borrador del panel lateral para comenzar.</div>
        )}
      </div>

      {/* Drawer de Trazabilidad */}
      <AnimatePresence>
        {drawerOpen && (
          <motion.div initial={{ x: 450 }} animate={{ x: 0 }} exit={{ x: 450 }} transition={{ type: 'spring', damping: 25, stiffness: 200 }} className="absolute right-0 top-0 h-full w-[400px] bg-[#0A0714] border-l border-white/10 z-50 flex flex-col shadow-[-20px_0_50px_rgba(0,0,0,0.5)]">
            <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
              <h3 className="font-bold text-sm text-white flex items-center gap-2"><MessageSquare className="w-4 h-4 text-blue-400"/> Mensajes Fuente Originales</h3>
              <button onClick={() => setDrawerOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div className="flex-1 p-5 overflow-y-auto flex flex-col gap-4">
              {selectedActivo?.fuentes_detalle?.map(f => (
                <div key={f.id_mensaje} className="bg-white/[0.03] border border-white/10 rounded-xl p-4">
                  <div className="flex justify-between mb-2">
                    <span className="text-xs font-semibold text-indigo-300">{f.autor}</span>
                    <span className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded text-slate-300">{f.canal}</span>
                  </div>
                  <p className="text-sm text-slate-200 italic leading-relaxed">"{f.texto}"</p>
                </div>
              ))}
              {(!selectedActivo?.fuentes_detalle || selectedActivo.fuentes_detalle.length === 0) && (
                 <p className="text-xs text-slate-500 text-center mt-10">No se encontraron fuentes detalladas para este activo.</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}