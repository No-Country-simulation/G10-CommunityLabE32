'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Database, LayoutDashboard, MessageSquare, UploadCloud, FileJson, CheckCircle2, AlertCircle, Loader2, Edit3 } from 'lucide-react';
import { motion } from 'framer-motion';
import { subirLote } from '@/services/api';

export default function IngestaPage() {
  const [origen, setOrigen] = useState('panel_local');
  const [periodo, setPeriodo] = useState('Semana 2');
  const [cierre, setCierre] = useState(false);
  const [trabajoId, setTrabajoId] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [completado, setCompletado] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validarYGuardarArchivo(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validarYGuardarArchivo(e.target.files[0]);
    }
  };

  const validarYGuardarArchivo = (archivo: File) => {
    if (archivo.type === "application/json" || archivo.name.endsWith('.jsonl') || archivo.name.endsWith('.csv') || archivo.name.endsWith('.json')) {
      setFile(archivo);
      setCompletado(false);
    } else {
      alert("Por favor, sube únicamente archivos JSON o CSV.");
    }
  };

  const procesarLote = async () => {
    if (!file) return;
    setProcesando(true);

    try {
      const respuesta = await subirLote(file, origen, periodo, cierre);
      console.log("Respuesta del servidor:", respuesta);
      setProcesando(false);
      setTrabajoId(respuesta.procesamiento_id);
      setCompletado(true);
    } catch (error) {
      console.error("Error subiendo el archivo:", error);
      alert("Hubo un error al procesar el archivo. Revisa la consola.");
      setProcesando(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0714] flex text-slate-200 selection:bg-purple-500/30 relative overflow-hidden">
      {/* Glow ambiental */}
      <div className="absolute -top-32 right-1/4 w-[450px] h-[450px] bg-indigo-600/20 rounded-full blur-[130px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[350px] h-[350px] bg-purple-600/15 rounded-full blur-[110px] pointer-events-none" />

      {/* Sidebar */}
      <aside className="w-60 border-r border-white/10 bg-white/[0.02] backdrop-blur-xl p-5 flex-col gap-8 hidden md:flex relative z-10">
        <div className="flex items-center gap-2.5 px-2 pt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.5)]">
            <Database className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-[15px] bg-gradient-to-r from-indigo-300 to-purple-300 bg-clip-text text-transparent">
            CommunityLab
          </span>
        </div>
        <nav className="flex flex-col gap-1.5">
          <Link
            href="/"
            className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium"
          >
            <LayoutDashboard className="w-4 h-4" /> Dashboard
          </Link>
          <Link
            href="/ingesta"
            className="flex items-center gap-3 text-white bg-gradient-to-r from-indigo-500/20 to-purple-500/10 border border-purple-500/30 px-3 py-2.5 rounded-xl text-sm font-medium shadow-[0_0_20px_rgba(139,92,246,0.15)]"
          >
            <UploadCloud className="w-4 h-4 text-purple-300" /> Ingesta de datos
          </Link>
          <Link
            href="/interacciones"
            className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium"
          >
            <MessageSquare className="w-4 h-4" /> Interacciones
          </Link>
          <Link
          href="/curaduria"
          className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium"
          >
            <Edit3 className="w-4 h-4" /> Curaduría
        </Link>
          
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10 max-w-5xl relative z-10">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-purple-300 bg-clip-text text-transparent">
            Ingesta de lotes
          </h1>
          <p className="text-slate-400 mt-1.5 text-[15px]">Sube archivos JSON o CSV para procesarlos mediante los agentes de IA.</p>
        </header>

        <div className="max-w-2xl bg-white/[0.03] backdrop-blur-xl rounded-2xl border border-white/10 p-7 shadow-[0_0_40px_rgba(139,92,246,0.08)]">
          <div className="mb-6">
            <h2 className="text-[15px] font-medium text-white">Fuente de datos</h2>
            <p className="text-sm text-slate-400 mt-1">El esquema del dataset se normaliza automáticamente antes de entrar al pipeline.</p>
          </div>

          <div className="flex flex-col gap-3 mb-5">
            <label>Comunidad <input className="bg-white/10 rounded p-2 ml-2" value={origen} onChange={e => setOrigen(e.target.value)} /></label>
            <label>Período <input className="bg-white/10 rounded p-2 ml-2" value={periodo} onChange={e => setPeriodo(e.target.value)} /></label>
            <label><input type="checkbox" checked={cierre} onChange={e => setCierre(e.target.checked)} /> Cerrar período y generar resumen</label>
          </div>
          <form onDragEnter={handleDrag} onSubmit={(e) => e.preventDefault()}>
            <input type="file" id="file-upload" className="hidden" accept=".json,.jsonl,.csv" onChange={handleChange} />
            <label
              htmlFor="file-upload"
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center w-full h-60 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-300 ${
                dragActive
                  ? 'border-purple-400/70 bg-purple-500/10 shadow-[0_0_40px_rgba(139,92,246,0.2)] scale-[1.01]'
                  : file
                  ? 'border-emerald-400/50 bg-emerald-500/5'
                  : 'border-white/15 hover:border-purple-400/40 hover:bg-white/[0.03]'
              }`}
            >
              <div className="flex flex-col items-center justify-center px-6 text-center">
                {file ? (
                  <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center">
                    <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center mb-4 shadow-[0_0_25px_rgba(52,211,153,0.3)]">
                      <FileJson className="w-8 h-8 text-emerald-300" />
                    </div>
                    <p className="mb-1.5 text-[15px] font-medium text-slate-100">Archivo listo para procesar</p>
                    <p className="text-xs text-emerald-300 font-mono bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
                      {file.name} · {(file.size / 1024).toFixed(2)} KB
                    </p>
                  </motion.div>
                ) : (
                  <>
                    <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-all duration-300 ${dragActive ? 'bg-purple-500/20 border border-purple-400/40 shadow-[0_0_25px_rgba(139,92,246,0.35)]' : 'bg-white/5 border border-white/10'}`}>
                      <UploadCloud className={`w-8 h-8 ${dragActive ? 'text-purple-300' : 'text-slate-400'}`} />
                    </div>
                    <p className="mb-1.5 text-[15px] text-slate-300">
                      <span className="font-semibold bg-gradient-to-r from-indigo-300 to-purple-300 bg-clip-text text-transparent">Haz clic para subir</span> o arrastra y suelta
                    </p>
                    <p className="text-xs text-slate-500">Formatos soportados: JSON, JSONL, CSV</p>
                  </>
                )}
              </div>
            </label>
          </form>

          {trabajoId && <p className="text-xs mt-3">Trabajo: {trabajoId}. <a className="underline" href={`/api/v1/trabajos/${trabajoId}`} target="_blank" rel="noreferrer">Consultar estado y resultado</a></p>}
          <div className="mt-7 pt-6 border-t border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2.5 text-sm">
              {procesando && (
                <span className="flex items-center gap-2.5 text-purple-300">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Procesando archivo…
                </span>
              )}
              {completado && (
                <motion.span
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 text-emerald-300"
                >
                  <CheckCircle2 className="w-4 h-4" /> Lote recibido; pendiente de procesamiento
                </motion.span>
              )}
              {!procesando && !completado && !file && (
                <span className="flex items-center gap-2 text-slate-500">
                  <AlertCircle className="w-4 h-4" /> Esperando dataset
                </span>
              )}
            </div>

            <button
              onClick={procesarLote}
              disabled={!file || procesando || completado}
              className={`px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 ${
                !file || procesando || completado
                  ? 'bg-white/5 text-slate-500 border border-white/10 cursor-not-allowed'
                  : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-[0_0_25px_rgba(139,92,246,0.35)] hover:shadow-[0_0_35px_rgba(139,92,246,0.55)] hover:-translate-y-0.5'
              }`}
            >
              {procesando ? 'Procesando…' : completado ? 'Recibido' : 'Iniciar procesamiento'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}