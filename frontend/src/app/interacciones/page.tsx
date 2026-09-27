'use client';

import { useEffect, useState } from 'react';
import { obtenerMensajes, Mensaje } from '@/services/api';
import { Database, LayoutDashboard, MessageSquare, Search, ChevronLeft, ChevronRight, Filter, UploadCloud, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { motion } from 'framer-motion';

export default function InteraccionesPage() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState('');
  const [paginaActual, setPaginaActual] = useState(1);
  const itemsPorPagina = 10;

  useEffect(() => {
    obtenerMensajes()
      .then((data) => {
        setMensajes(data);
        setCargando(false);
      })
      .catch((err) => {
        console.error("Error conectando al backend:", err);
        setCargando(false);
      });
  }, []);

  const mensajesFiltrados = mensajes.filter(msg =>
    msg.texto.toLowerCase().includes(busqueda.toLowerCase()) ||
    msg.autor.toLowerCase().includes(busqueda.toLowerCase())
  );

  const totalPaginas = Math.ceil(mensajesFiltrados.length / itemsPorPagina);
  const indiceUltimoItem = paginaActual * itemsPorPagina;
  const indicePrimerItem = indiceUltimoItem - itemsPorPagina;
  const mensajesPaginados = mensajesFiltrados.slice(indicePrimerItem, indiceUltimoItem);

  const sentimentStyles: Record<string, string> = {
    positivo: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    negativo: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  };

  return (
    <div className="min-h-screen bg-[#0A0714] flex text-slate-200 relative overflow-hidden">
      {/* Glow ambiental */}
      <div className="absolute top-0 right-0 w-[450px] h-[450px] bg-purple-600/15 rounded-full blur-[130px] pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-[350px] h-[350px] bg-indigo-600/15 rounded-full blur-[110px] pointer-events-none" />

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
            className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium"
          >
            <UploadCloud className="w-4 h-4" /> Ingesta de datos
          </Link>
          <Link
            href="/interacciones"
            className="flex items-center gap-3 text-white bg-gradient-to-r from-indigo-500/20 to-purple-500/10 border border-purple-500/30 px-3 py-2.5 rounded-xl text-sm font-medium shadow-[0_0_20px_rgba(139,92,246,0.15)]"
          >
            <MessageSquare className="w-4 h-4 text-purple-300" /> Interacciones
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-10 flex flex-col h-screen overflow-hidden relative z-10">
        <header className="mb-6 shrink-0">
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-purple-300 bg-clip-text text-transparent">
            Interacciones ingeridas
          </h1>
          <p className="text-slate-400 mt-1.5 text-[15px]">Explora, busca y filtra la base de conocimiento comunitaria.</p>
        </header>

        <div className="flex justify-between items-center mb-5 shrink-0">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Buscar por contenido o autor…"
              className="block w-full pl-10 pr-3 py-2.5 rounded-xl bg-white/[0.03] backdrop-blur-xl border border-white/10 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-400/50 focus:ring-1 focus:ring-purple-400/50 transition-colors"
              value={busqueda}
              onChange={(e) => {
                setBusqueda(e.target.value);
                setPaginaActual(1);
              }}
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-slate-300 text-sm font-medium hover:text-white hover:border-purple-400/30 transition-colors">
            <Filter className="w-4 h-4" /> Filtros avanzados
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white/[0.03] backdrop-blur-xl rounded-2xl border border-white/10 flex-1 overflow-hidden flex flex-col shadow-[0_0_40px_rgba(139,92,246,0.08)]"
        >
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10">
              <thead>
                <tr>
                  <th scope="col" className="px-5 py-3.5 text-left text-xs font-medium text-slate-400">Autor</th>
                  <th scope="col" className="px-5 py-3.5 text-left text-xs font-medium text-slate-400">Mensaje</th>
                  <th scope="col" className="px-5 py-3.5 text-left text-xs font-medium text-slate-400">Canal</th>
                  <th scope="col" className="px-5 py-3.5 text-left text-xs font-medium text-slate-400">Sentimiento</th>
                  <th scope="col" className="px-5 py-3.5 text-left text-xs font-medium text-slate-400">Fecha</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {cargando ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-14 text-center text-slate-500 text-sm">
                      <span className="inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin text-purple-400" /> Cargando base de datos…</span>
                    </td>
                  </tr>
                ) : mensajesPaginados.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-14 text-center text-slate-500 text-sm">No se encontraron resultados para "{busqueda}"</td>
                  </tr>
                ) : (
                  mensajesPaginados.map((msg) => (
                    <tr key={msg.id_mensaje} className="hover:bg-white/[0.03] transition-colors">
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-[11px] font-bold shrink-0 shadow-[0_0_12px_rgba(139,92,246,0.4)]">
                            {msg.autor.substring(0, 2).toUpperCase()}
                          </div>
                          <span className="text-sm font-medium text-slate-200">{msg.autor}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm text-slate-400 line-clamp-2 max-w-xl" title={msg.texto}>
                          {msg.texto}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                          {msg.canal}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${sentimentStyles[msg.sentimiento_ref ?? ''] ?? 'bg-white/5 text-slate-300 border-white/10'}`}>
                          {msg.sentimiento_ref || 'N/A'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap text-sm text-slate-500">
                        {new Date(msg.fecha).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-5 py-3.5 border-t border-white/10 flex items-center justify-between shrink-0">
            <div className="text-sm text-slate-500">
              Mostrando <span className="text-slate-300 font-medium">{mensajesFiltrados.length > 0 ? indicePrimerItem + 1 : 0}</span> a <span className="text-slate-300 font-medium">{Math.min(indiceUltimoItem, mensajesFiltrados.length)}</span> de <span className="text-slate-300 font-medium">{mensajesFiltrados.length}</span> resultados
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPaginaActual(p => Math.max(1, p - 1))}
                disabled={paginaActual === 1}
                className="p-2 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:border-purple-400/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPaginaActual(p => Math.min(totalPaginas, p + 1))}
                disabled={paginaActual === totalPaginas || totalPaginas === 0}
                className="p-2 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:border-purple-400/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}