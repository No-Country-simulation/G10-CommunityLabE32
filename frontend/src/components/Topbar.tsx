'use client';

import { usePathname } from 'next/navigation';
import { useSyncExternalStore } from 'react';
import { Sun, Moon } from 'lucide-react';

type Tema = 'light' | 'dark';

const secciones: Record<string, string> = {
  '/': 'Centro de Operaciones',
  '/ingesta': 'Ingesta de lotes',
  '/interacciones': 'Interacciones',
  '/curaduria': 'Curaduría',
};

const subscribe = (cb: () => void) => {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  return () => obs.disconnect();
};
const getSnapshot = (): Tema =>
  document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
const getServerSnapshot = (): Tema => 'light';

export default function Topbar() {
  const pathname = usePathname();
  const tema = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const seccion =
    secciones[pathname] ??
    Object.entries(secciones).find(([ruta]) => ruta !== '/' && pathname.startsWith(ruta))?.[1] ??
    '';

  const elegirTema = (nuevo: Tema) => {
    document.documentElement.dataset.theme = nuevo;
    try {
      localStorage.setItem('theme', nuevo);
    } catch {}
  };

  const base =
    'flex items-center gap-1.5 h-8 px-3.5 rounded-full text-xs font-medium transition-colors';
  const activo = 'bg-primary text-white shadow-sm';
  const inactivo = 'text-sidebar-foreground hover:text-white';

  return (
    <header
      className="sticky top-0 z-30 grid grid-cols-[1fr_auto_1fr] items-center bg-sidebar border-b border-sidebar-border px-6 shadow-md"
      style={{ height: 'var(--topbar-h)' }}
    >
      {/* Izquierda: título de la sección */}
      <div className="min-w-0 hidden sm:block">
        {seccion && (
          <div className="border-l-2 border-primary-bright pl-3 leading-tight">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">
              Sección
            </p>
            <p className="text-base font-semibold text-white truncate">{seccion}</p>
          </div>
        )}
      </div>
      <div className="sm:hidden" />

      {/* Centro: logo + nombre */}
      <div className="flex items-center justify-center gap-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="CommunityLab" className="w-11 h-11 rounded-xl shadow-lg shrink-0" />
        <span className="font-extrabold text-2xl tracking-tight text-white whitespace-nowrap">
          CommunityLab
        </span>
      </div>

      {/* Derecha: selector de tema */}
      <div className="flex justify-end">
        <div
          role="group"
          aria-label="Tema de la interfaz"
          className="flex items-center rounded-full border border-sidebar-border bg-sidebar-active p-0.5 shrink-0"
        >
          <button
            onClick={() => elegirTema('light')}
            aria-pressed={tema === 'light'}
            className={`${base} ${tema === 'light' ? activo : inactivo}`}
          >
            <Sun className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Claro</span>
          </button>
          <button
            onClick={() => elegirTema('dark')}
            aria-pressed={tema === 'dark'}
            className={`${base} ${tema === 'dark' ? activo : inactivo}`}
          >
            <Moon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Oscuro</span>
          </button>
        </div>
      </div>
    </header>
  );
}