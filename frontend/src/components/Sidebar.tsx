'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, UploadCloud, Edit3 } from 'lucide-react';

const items = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/ingesta', label: 'Ingesta', icon: UploadCloud },
  { href: '/interacciones', label: 'Interacciones', icon: MessageSquare },
  { href: '/curaduria', label: 'Curaduría', icon: Edit3 },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
    {/* Móvil: barra inferior fija para mantener visible la navegación entre secciones */}
    <nav
      aria-label="Navegación principal"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 grid grid-cols-4 bg-sidebar border-t border-sidebar-border shadow-md"
    >
      {items.map(({ href, label, icon: Icon }) => {
        const activo = href === '/' ? pathname === '/' : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={activo ? 'page' : undefined}
            className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors ${
              activo ? 'text-primary-bright' : 'text-sidebar-foreground hover:text-white'
            }`}
          >
            <Icon className="w-5 h-5" />
            {label}
          </Link>
        );
      })}
    </nav>
    <aside className="hidden md:flex w-60 shrink-0 flex-col gap-3 bg-sidebar border-r border-sidebar-border p-5 sticky top-[var(--topbar-h)] h-screen">
      <p className="px-3 pt-1 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/50">
        Navegación
      </p>
      <nav className="flex flex-col gap-1">
        {items.map(({ href, label, icon: Icon }) => {
          const activo = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <Link key={href} href={href} aria-current={activo ? 'page' : undefined} className={activo ? 'nav-item-active' : 'nav-item'}>
              <Icon className={`w-4 h-4 ${activo ? 'text-primary-bright' : ''}`} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
    </>
  );
}