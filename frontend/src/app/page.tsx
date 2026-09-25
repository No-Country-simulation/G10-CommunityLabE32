"use client";

import { useState } from "react";

interface Activo {
  id_activo: string;
  formato: string;
  copy: string;
  fuentes: string[];
  estado: string;
}

interface Alerta {
  id_alerta: string;
  nivel: string;
  mensaje: string;
  fuente: string;
}

export default function Home() {
  const [cargando, setCargando] = useState(false);
  const [activos, setActivos] = useState<Activo[]>([]);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [resumen, setResumen] = useState("");
  const [filtro, setFiltro] = useState<string>("todos");

  const probarApiBackend = async () => {
    setCargando(true);
    try {
      const respuesta = await fetch("http://127.0.0.1:8000/api/v1/procesamientos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origen_comunidad: "discord_comunidad_alura",
          periodo_referencia: "2026-W38",
          interacciones: [
            {
              id: "m-01",
              autor: "carlos_dev",
              canal: "logros",
              fecha: "2026-09-23T10:00:00Z",
              texto: "Conseguí trabajo como Dev Jr tras publicar mi app con IA."
            }
          ]
        })
      });

      if (!respuesta.ok) throw new Error("Error en la respuesta del backend");

      const data = await respuesta.json();
      setResumen(data.resumen_comunidad);
      setActivos(data.activos_distribucion_generados);
      setAlertas(data.alertas_internas);
    } catch (error) {
      alert("No se pudo conectar con FastAPI en http://127.0.0.1:8000. Revisa que el backend esté encendido.");
    } finally {
      setCargando(false);
    }
  };

  const activosFiltrados = filtro === "todos" 
    ? activos 
    : activos.filter(a => a.formato.toLowerCase() === filtro.toLowerCase());

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Barra de navegación superior */}
      <nav className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center font-black text-white text-lg shadow-lg shadow-indigo-500/20">
              CL
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white tracking-tight">CommunityLab</span>
                <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  MVP v0.1
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Motor de Transformación y Curaduría</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-300 font-medium">OCI Compute A1</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-400 text-xs font-semibold">
              Bucket Always Free
            </div>
          </div>
        </div>
      </nav>

      {/* Contenedor principal */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full space-y-8">
        {/* Banner de Bienvenida y Disparador de Mock */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 p-8 shadow-2xl">
          <div className="max-w-2xl relative z-10 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-950/60 px-2.5 py-1 rounded-md border border-indigo-800/50">
              Sprint 1 • Tarea 8 & 9
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Panel de Ingesta y Curaduría Comunitaria
            </h2>
            <p className="text-slate-300 text-sm leading-relaxed">
              Transformación automatizada de mensajes de Discord hacia copys listos para redes, bases técnicas FAQ y resúmenes semanales con persistencia en Oracle Cloud.
            </p>
            <div className="pt-2">
              <button
                onClick={probarApiBackend}
                disabled={cargando}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-semibold text-sm transition-all shadow-lg shadow-indigo-600/30 disabled:opacity-50"
              >
                {cargando ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    Procesando con FastAPI...
                  </>
                ) : (
                  <>⚡ Disparar Ingesta Mock (API POST)</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Tarjetas KPI de Estado */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <div className="text-xs font-medium text-slate-400">Total Mensajes</div>
            <div className="text-2xl font-bold text-white mt-1">{activos.length > 0 ? "6" : "0"}</div>
            <div className="text-[11px] text-slate-500 mt-1">Lote 2026-W38</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <div className="text-xs font-medium text-slate-400">Activos Creados</div>
            <div className="text-2xl font-bold text-indigo-400 mt-1">{activos.length}</div>
            <div className="text-[11px] text-slate-500 mt-1">Rutas 1, 2 y 3</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <div className="text-xs font-medium text-slate-400">Alertas Internas</div>
            <div className="text-2xl font-bold text-rose-400 mt-1">{alertas.length}</div>
            <div className="text-[11px] text-slate-500 mt-1">Ruta 4 (Bloqueos)</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <div className="text-xs font-medium text-slate-400">Destino Storage</div>
            <div className="text-sm font-semibold text-emerald-400 mt-2 truncate">OCI /lotes/paquete.json</div>
            <div className="text-[11px] text-slate-500 mt-1">Persistencia activa</div>
          </div>
        </div>

        {/* Alerta Interna (Ruta 4 de Zeus) */}
        {alertas.length > 0 && (
          <div className="bg-rose-950/20 border border-rose-900/60 rounded-xl p-5 shadow-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping"></span>
              <h4 className="text-rose-400 font-bold text-sm tracking-wide uppercase">
                Alerta Crítica Interna Detectada (Ruta 4 — No para publicación)
              </h4>
            </div>
            {alertas.map((alerta) => (
              <div key={alerta.id_alerta} className="flex justify-between items-center text-xs text-rose-200/90 bg-rose-950/40 p-3 rounded-lg border border-rose-900/30">
                <span>{alerta.mensaje}</span>
                <span className="font-mono bg-rose-900/40 px-2 py-0.5 rounded text-rose-300">
                  Fuente: {alerta.fuente}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Sección de Activos de Marketing */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800">
            <div>
              <h3 className="text-lg font-bold text-white">Borradores Generados para Curaduría</h3>
              <p className="text-xs text-slate-400">Revisa, edita o aprueba antes de sincronizar con OCI</p>
            </div>
            
            {/* Filtros */}
            <div className="flex gap-1.5 bg-slate-900 p-1 rounded-xl border border-slate-800">
              {["todos", "linkedin", "faq", "newsletter"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setFiltro(tab)}
                  className={`text-xs px-3 py-1.5 rounded-lg capitalize font-medium transition-all ${
                    filtro === tab
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {/* Grilla de Activos */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {activosFiltrados.length > 0 ? (
              activosFiltrados.map((activo) => (
                <div
                  key={activo.id_activo}
                  className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all shadow-md hover:shadow-indigo-950/20"
                >
                  <div>
                    <div className="flex justify-between items-start mb-3">
                      <span className={`text-[10px] uppercase tracking-wider font-extrabold px-2.5 py-1 rounded-lg border ${
                        activo.formato === "linkedin"
                          ? "bg-blue-950/60 text-blue-400 border-blue-800/60"
                          : activo.formato === "faq"
                          ? "bg-amber-950/60 text-amber-400 border-amber-800/60"
                          : "bg-purple-950/60 text-purple-400 border-purple-800/60"
                      }`}>
                        {activo.formato}
                      </span>
                      <span className="text-[11px] font-mono text-slate-500">
                        {activo.fuentes.join(", ")}
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed font-normal">
                      {activo.copy}
                    </p>
                  </div>

                  <div className="pt-4 mt-4 border-t border-slate-800/80 flex gap-2">
                    <button className="flex-1 py-1.5 px-3 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold transition-colors">
                      ✓ Aprobar
                    </button>
                    <button className="flex-1 py-1.5 px-3 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-colors">
                      ✎ Editar
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-3 text-center py-16 border-2 border-dashed border-slate-800/80 rounded-2xl bg-slate-900/20 space-y-2">
                <div className="text-2xl">⚡</div>
                <div className="text-sm font-medium text-slate-300">No hay activos cargados todavía</div>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Presiona el botón superior <strong className="text-indigo-400">"Disparar Ingesta Mock"</strong> para consultar el backend y ver la generación en vivo.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Pie de página */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500">
        CommunityLab MVP • Hackathon ONE G10-LATAM • Oracle Cloud Infrastructure
      </footer>
    </div>
  );
}