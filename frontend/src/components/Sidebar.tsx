'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard, MessageSquare, UploadCloud, Edit3, Sparkles, LogOut, BarChart3, Users, Settings,
} from 'lucide-react';
import { cerrarSesion } from '@/services/api';

const itemsPrincipales = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/analitica', label: 'Analítica y Gráficas', icon: BarChart3 },
  { href: '/ingesta', label: 'Ingesta', icon: UploadCloud },
  { href: '/interacciones', label: 'Interacciones', icon: MessageSquare },
  { href: '/curaduria', label: 'Curaduría', icon: Edit3 },
];

const itemsSistema = [
  { href: '/equipo', label: 'Acerca del Equipo', icon: Users },
  { href: '/configuracion', label: 'Configuración', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const manejarSalida = () => {
    cerrarSesion();
    router.push('/login');
  };

  return (
    <>
      {/* Móvil: barra inferior fija con fondo oscuro Azure */}
      <nav
        aria-label="Navegación principal"
        className="md:hidden fixed bottom-0 inset-x-0 z-40 grid grid-cols-5 bg-[#0a192f] border-t border-white/10 shadow-lg"
      >
        {[...itemsPrincipales.slice(0, 4), itemsSistema[1]].map(({ href, label, icon: Icon }) => {
          const activo = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={activo ? 'page' : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-all ${
                activo ? 'text-cyan-400 scale-105' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span className="truncate max-w-[64px]">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Escritorio: Sidebar con degradado vertical y cápsula activa brillante */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col justify-between sidebar-container p-4 sticky top-[var(--topbar-h)] h-[calc(100dvh-var(--topbar-h))] shadow-2xl z-20 overflow-y-auto">
        <div className="flex flex-col gap-5">
          {/* Módulos Operativos */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 px-3 pt-2 mb-1">
              <div className="h-6 w-6 rounded-md bg-gradient-to-tr from-cyan-400 to-blue-600 flex items-center justify-center shadow-sm shadow-cyan-500/40">
                <Sparkles className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-cyan-300/80">
                Módulos Activos
              </span>
            </div>

            <nav className="flex flex-col gap-1.5">
              {itemsPrincipales.map(({ href, label, icon: Icon }) => {
                const activo = href === '/' ? pathname === '/' : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={activo ? 'page' : undefined}
                    className={`group ${activo ? 'nav-item-active' : 'nav-item'}`}
                  >
                    <Icon
                      className={`w-4 h-4 transition-transform duration-200 ${
                        activo
                          ? 'text-white scale-110'
                          : 'text-slate-300 group-hover:text-white group-hover:scale-110'
                      }`}
                    />
                    <span>{label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Módulos de Organización y Cuenta */}
          <div className="flex flex-col gap-2 pt-3 border-t border-white/10">
            <span className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400/80">
              Plataforma y Cuenta
            </span>
            <nav className="flex flex-col gap-1.5">
              {itemsSistema.map(({ href, label, icon: Icon }) => {
                const activo = pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={activo ? 'page' : undefined}
                    className={`group ${activo ? 'nav-item-active' : 'nav-item'}`}
                  >
                    <Icon
                      className={`w-4 h-4 transition-transform duration-200 ${
                        activo
                          ? 'text-white scale-110'
                          : 'text-slate-300 group-hover:text-white group-hover:scale-110'
                      }`}
                    />
                    <span>{label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Pie del Sidebar con botón Cerrar Sesión en ROJO PURO al pasar el mouse */}
        <div className="border-t border-white/10 pt-3 px-2 flex flex-col gap-3 mt-4">
          <button
            type="button"
            onClick={manejarSalida}
            className="group w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-red-600/85 border border-red-500 hover:bg-red-600 hover:border-red-400 hover:shadow-[0_0_20px_rgba(239,68,68,0.65)] active:scale-[0.98] transition-all duration-200 cursor-pointer"
          >
            <LogOut className="w-4 h-4 shrink-0 transition-transform duration-200 group-hover:-translate-x-0.5" />
            <span>Cerrar Sesión</span>
          </button>
          <p className="text-[11px] text-center text-slate-400/70 font-medium">
            CommunityLab • Equipo 32
          </p>
        </div>
      </aside>
    </>
  );
}