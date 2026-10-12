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
    <aside className="hidden md:flex w-60 shrink-0 flex-col gap-3 bg-sidebar border-r border-sidebar-border p-5 sticky top-[var(--topbar-h)] h-screen">
      <p className="px-3 pt-1 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/50">
        Navegación
      </p>
      <nav className="flex flex-col gap-1">
        {items.map(({ href, label, icon: Icon }) => {
          const activo = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={activo ? 'nav-item-active' : 'nav-item'}>
              <Icon className={`w-4 h-4 ${activo ? 'text-primary-bright' : ''}`} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}