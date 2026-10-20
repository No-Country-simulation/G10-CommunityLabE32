'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Sun, Moon } from 'lucide-react';

const titulos: Record<string, string> = {
  '/': 'Dashboard',
  '/analitica': 'Analítica',
  '/ingesta': 'Ingesta',
  '/interacciones': 'Interacciones',
  '/curaduria': 'Curaduría',
  '/equipo': 'Equipo 32',
  '/configuracion': 'Configuración',
};

export default function Topbar() {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    // Usamos un setTimeout para evitar el setState sincrónico dentro del effect que rechaza ESLint
    const timer = setTimeout(() => {
      setMounted(true);
      const actual = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
      setTheme(actual);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const cambiarTema = (nuevo: 'light' | 'dark') => {
    setTheme(nuevo);
    document.documentElement.dataset.theme = nuevo;
    try {
      localStorage.setItem('theme', nuevo);
    } catch {}
  };

  const seccion =
    Object.entries(titulos).find(([ruta]) =>
      ruta === '/' ? pathname === '/' : pathname.startsWith(ruta)
    )?.[1] ?? 'Panel';

  return (
    <header className="sticky top-0 z-30 h-[var(--topbar-h)] w-full bg-[#091931] border-b border-[#193257] px-4 sm:px-6 flex items-center justify-between text-white shadow-md">
      {/* Izquierda: Indicador de sección */}
      <div className="flex items-center gap-3">
        <div className="h-8 w-1 rounded-full bg-gradient-to-b from-cyan-400 to-blue-600 shadow-[0_0_10px_rgba(0,180,216,0.8)]" />
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-cyan-300/80">
            Sección
          </p>
          <p className="text-sm font-bold text-white leading-tight">{seccion}</p>
        </div>
      </div>

      {/* Centro: Logo */}
      <div className="flex items-center gap-3.5 group cursor-pointer">
        <div className="h-12 w-12 rounded-xl overflow-hidden bg-white flex items-center justify-center shadow-[0_0_18px_rgba(0,180,216,0.55)] border-2 border-cyan-400/50 transition-transform duration-200 group-hover:scale-110">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/comunity.png"
            alt="CommunityLab Logo"
            className="h-full w-full object-cover object-top scale-125"
          />
        </div>
        <span className="text-xl sm:text-2xl font-extrabold tracking-tight text-white group-hover:text-cyan-300 transition-colors">
          Community<span className="text-cyan-400">Lab</span>
        </span>
      </div>

      {/* Derecha: Selector Claro / Oscuro */}
      <div className="flex items-center gap-1 bg-[#0c2547] p-1 rounded-full border border-white/10" suppressHydrationWarning>
        <button
          type="button"
          onClick={() => cambiarTema('light')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            mounted && theme === 'light'
              ? 'bg-gradient-to-r from-[#0077e6] to-[#00b4d8] text-white shadow-[0_0_12px_rgba(0,180,216,0.5)]'
              : 'text-slate-300 hover:bg-[#0077e6]/40 hover:text-white'
          }`}
        >
          <Sun className="w-3.5 h-3.5" />
          <span>Claro</span>
        </button>
        <button
          type="button"
          onClick={() => cambiarTema('dark')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            mounted && theme === 'dark'
              ? 'bg-gradient-to-r from-[#0077e6] to-[#00b4d8] text-white shadow-[0_0_12px_rgba(0,180,216,0.5)]'
              : 'text-slate-300 hover:bg-[#0077e6]/40 hover:text-white'
          }`}
        >
          <Moon className="w-3.5 h-3.5" />
          <span>Oscuro</span>
        </button>
      </div>
    </header>
  );
}