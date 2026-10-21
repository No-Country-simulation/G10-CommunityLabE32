'use client';

import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, UploadCloud, Edit3, BarChart3, Users, Settings, MoreHorizontal, ArrowUpRight } from 'lucide-react';
const items = [
  { href: '/', label: 'Resumen', icon: LayoutDashboard },
  { href: '/ingesta', label: 'Ingesta de datos', icon: UploadCloud },
  { href: '/interacciones', label: 'Interacciones', icon: MessageSquare },
  { href: '/curaduria', label: 'Curaduría', icon: Edit3 },
  { href: '/analitica', label: 'Analítica', icon: BarChart3 },
];
export default function Sidebar() {
  const pathname = usePathname();
  return <UiTree>{<>
    <nav className="workspace-mobile" aria-label="Navegación móvil">{items.map(({href,label,icon:Icon}) => <Link key={href} href={href} aria-label={label} aria-current={pathname === href ? 'page' : undefined}><Icon size={18} /></Link>)}<Link href="/configuracion" aria-label="Configuración"><Settings size={18}/></Link></nav>
    <aside id="sidebar-principal" className="workspace-sidebar" aria-label="Menú lateral">
      <nav className="workspace-nav" aria-label="Módulos de CommunityLab">{items.map(({href,label,icon:Icon}) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined}><Icon size={15} /><span>{label}</span></Link>)}</nav>
      <div className="workspace-sidebar-bottom">
        <details className="workspace-account"><summary><span className="workspace-avatar small">CL</span><span>Mi cuenta</span><MoreHorizontal size={16}/></summary><div className="workspace-account-menu"><strong translate="no" className="notranslate">CommunityLab</strong><p>Espacio de tu comunidad</p><Link href="/configuracion"><Settings size={14}/>Cuenta y seguridad</Link><Link href="/equipo"><Users size={14}/>Acerca del equipo</Link><Link href="/login"><ArrowUpRight size={14}/>Ver inicio de sesión</Link></div></details>
      </div>
    </aside>
  </>}</UiTree>;
}
