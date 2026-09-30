'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { obtenerMensajes, obtenerKPIs, Mensaje, DashboardKPIs } from '@/services/api';
import { 
  Database, LayoutDashboard, MessageSquare, UploadCloud, 
  Loader2, Wifi, Edit3, Layers, CheckCircle2, AlertTriangle, Activity 
} from 'lucide-react';
import { motion } from 'framer-motion';

export default function CommunityDashboard() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    // Carga paralela de KPIs y Mensajes (Motor PostgreSQL)
    Promise.all([obtenerKPIs(), obtenerMensajes()])
      .then(([kpiData, msgsData]) => {
        setKpis(kpiData);
        setMensajes(msgsData.items);
        setCargando(false);
      })
      .catch((err) => {
        console.error("Error conectando al backend:", err);
        setCargando(false);
      });
  }, []);

  const sentimentStyles: Record<string, string> = {
    positivo: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    negativo: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  };

  return (
    <div className="min-h-screen bg-[#0A0714] flex text-slate-200 selection:bg-purple-500/30 relative overflow-hidden">
      {/* Glow ambiental */}
      <div className="absolute -top-40 left-1/3 w-[500px] h-[500px] bg-purple-600/20 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-indigo-600/15 rounded-full blur-[120px] pointer-events-none" />

      {/* Sidebar */}
      <aside className="w-60 border-r border-white/10 bg-white/[0.02] backdrop-blur-xl p-5 flex-col gap-8 hidden md:flex relative z-10 shrink-0">
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
            className="flex items-center gap-3 text-white bg-gradient-to-r from-indigo-500/20 to-purple-500/10 border border-purple-500/30 px-3 py-2.5 rounded-xl text-sm font-medium shadow-[0_0_20px_rgba(139,92,246,0.15)]"
          >
            <LayoutDashboard className="w-4 h-4 text-purple-300" /> Dashboard
          </Link>
          <Link
            href="/ingesta"
            className="flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent px-3 py-2.5 rounded-xl transition-colors text-sm font-medium"
          >
            <UploadCloud className="w-4 h-4" /> Ingesta de datos
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

      {/* Main Content */}
      <main className="flex-1 p-10 relative z-10 h-screen overflow-y-auto">
        <header className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold tracking-tight mb-1.5 bg-gradient-to-r from-white via-indigo-200 to-purple-300 bg-clip-text text-transparent">
              Centro de Operaciones
            </h1>
            <p className="text-slate-400 text-[15px]">Métricas en tiempo real e interacciones procesadas.</p>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold shadow-[0_0_20px_rgba(16,185,129,0.15)]">
            <Wifi className="w-3.5 h-3.5" />
            API conectada
          </div>
        </header>

        {cargando ? (
          <div className="flex items-center justify-center h-72 rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-xl">
            <div className="text-slate-400 flex items-center gap-3 text-sm">
              <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
              Sincronizando datos…
            </div>
          </div>
        ) : (
          <motion.div initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.1 } } }} className="space-y-8">
            
            {/* TAREA 3: TARJETAS DE KPIs */}
            {kpis && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-white/[0.03] backdrop-blur-xl p-5 rounded-2xl border border-white/10 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-all" />
                  <div className="flex items-center gap-3 mb-2 text-slate-400">
                    <MessageSquare className="w-5 h-5 text-blue-400" />
                    <span className="text-sm font-medium">Total Mensajes</span>
                  </div>
                  <h3 className="text-3xl font-bold text-white">{kpis.total_mensajes}</h3>
                  <div className="mt-3 text-xs text-slate-500 flex justify-between">
                    <span className="text-emerald-400">+{kpis.distribucion_sentimiento?.positivo || 0} positivos</span>
                    <span className="text-rose-400">{kpis.distribucion_sentimiento?.negativo || 0} quejas</span>
                  </div>
                </motion.div>

                <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-white/[0.03] backdrop-blur-xl p-5 rounded-2xl border border-white/10 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl group-hover:bg-purple-500/20 transition-all" />
                  <div className="flex items-center gap-3 mb-2 text-slate-400">
                    <Layers className="w-5 h-5 text-purple-400" />
                    <span className="text-sm font-medium">Borradores IA</span>
                  </div>
                  <h3 className="text-3xl font-bold text-white">{kpis.activos_generados}</h3>
                  <p className="mt-3 text-xs text-slate-500">Activos listos para revisión en el panel</p>
                </motion.div>

                <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-white/[0.03] backdrop-blur-xl p-5 rounded-2xl border border-white/10 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl group-hover:bg-emerald-500/20 transition-all" />
                  <div className="flex items-center gap-3 mb-2 text-slate-400">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span className="text-sm font-medium">Publicaciones</span>
                  </div>
                  <h3 className="text-3xl font-bold text-white">{kpis.activos_aprobados}</h3>
                  <p className="mt-3 text-xs text-slate-500">Aprobados listos para OCI Storage</p>
                </motion.div>

                <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-white/[0.03] backdrop-blur-xl p-5 rounded-2xl border border-rose-500/20 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-rose-500/10 rounded-full blur-2xl group-hover:bg-rose-500/20 transition-all" />
                  <div className="flex items-center gap-3 mb-2 text-rose-300">
                    <AlertTriangle className="w-5 h-5 text-rose-400" />
                    <span className="text-sm font-medium">Alertas Internas</span>
                  </div>
                  <h3 className="text-3xl font-bold text-white">{kpis.alertas_internas}</h3>
                  <p className="mt-3 text-xs text-slate-400">Bloqueos que requieren atención manual</p>
                </motion.div>
              </div>
            )}

            {/* SECCIÓN INFERIOR: FLUJO EN TIEMPO REAL */}
            <div>
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-indigo-400" /> Flujo en tiempo real
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {mensajes.slice(0, 9).map((msg) => (
                  <motion.div
                    variants={{ hidden: { opacity: 0, scale: 0.95 }, show: { opacity: 1, scale: 1 } }}
                    key={msg.id_mensaje}
                    className="bg-white/[0.03] backdrop-blur-xl p-5 rounded-2xl border border-white/10 hover:border-purple-500/40 transition-all duration-300 flex flex-col justify-between hover:shadow-[0_0_35px_rgba(139,92,246,0.15)] hover:-translate-y-0.5"
                  >
                    <div>
                      <div className="flex justify-between items-start mb-4">
                        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                          {msg.canal}
                        </span>
                        {msg.sentimiento_ref && (
                          <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${sentimentStyles[msg.sentimiento_ref] ?? 'bg-white/5 text-slate-300 border-white/10'}`}>
                            {msg.sentimiento_ref}
                          </span>
                        )}
                      </div>
                      <p className="text-slate-300 text-sm leading-relaxed mb-5 line-clamp-4">{msg.texto}</p>
                    </div>
                    <div className="pt-4 border-t border-white/10 flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-[0_0_15px_rgba(139,92,246,0.4)]">
                        {msg.autor.substring(0, 2).toUpperCase()}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-slate-200">{msg.autor}</span>
                        <span className="text-xs text-slate-500">{new Date(msg.fecha).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}