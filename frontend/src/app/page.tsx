'use client';

import { useEffect, useState } from 'react';
import { obtenerMensajes, Mensaje } from '@/services/api';
import { Database, LayoutDashboard, MessageSquare, ShieldAlert, Terminal } from 'lucide-react';
import { motion } from 'framer-motion';

export default function CommunityDashboard() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    // Llamada real a tu base de datos FastAPI
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

  return (
    <div className="min-h-screen bg-gray-50 flex text-gray-900">
      {/* Sidebar B2B */}
      <aside className="w-64 bg-slate-900 text-slate-300 p-6 flex flex-col gap-6 shadow-xl z-10 hidden md:flex">
        <div className="flex items-center gap-3 text-white font-bold text-xl tracking-wide">
          <Database className="w-6 h-6 text-blue-400" />
          CommunityLab
        </div>
        <nav className="flex flex-col gap-2 mt-4">
          <a href="#" className="flex items-center gap-3 bg-blue-600/20 text-blue-400 px-4 py-3 rounded-lg transition-colors font-medium">
            <LayoutDashboard className="w-5 h-5" /> Ingesta de Datos
          </a>
          <a href="#" className="flex items-center gap-3 hover:bg-slate-800 px-4 py-3 rounded-lg transition-colors">
            <MessageSquare className="w-5 h-5" /> Interacciones
          </a>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8">
        <header className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Panel de Curaduría</h1>
            <p className="text-slate-500 mt-1">Datos ingeridos directamente desde PostgreSQL / SQLite.</p>
          </div>
          <div className="flex items-center gap-2 bg-emerald-100 text-emerald-700 px-4 py-2 rounded-full text-sm font-semibold shadow-sm">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            API Conectada
          </div>
        </header>

        {cargando ? (
          <div className="flex items-center justify-center h-64 border-2 border-dashed border-gray-300 rounded-xl">
            <div className="text-gray-400 font-medium flex flex-col items-center gap-3">
              <Terminal className="w-8 h-8 animate-pulse text-blue-500" />
              Sincronizando con Backend...
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {mensajes.slice(0, 9).map((msg, index) => (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                key={msg.id_mensaje} 
                className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start mb-4">
                    <span className="text-xs font-bold px-3 py-1 rounded-full bg-slate-100 text-slate-600 uppercase tracking-wider">
                      {msg.canal}
                    </span>
                    {msg.sentimiento_ref && (
                      <span className={`text-xs font-bold px-3 py-1 rounded-full ${msg.sentimiento_ref === 'positivo' ? 'bg-green-100 text-green-700' : msg.sentimiento_ref === 'negativo' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`}>
                        {msg.sentimiento_ref}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-800 text-sm leading-relaxed mb-4 line-clamp-4">"{msg.texto}"</p>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-50 flex items-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-500 flex items-center justify-center text-white text-xs font-bold shadow-inner">
                    {msg.autor.substring(0, 2).toUpperCase()}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-gray-900">{msg.autor}</span>
                    <span className="text-xs text-gray-400">{new Date(msg.fecha).toLocaleDateString()}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}