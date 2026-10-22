'use client';
import { useEffect, useState } from 'react';
import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, UploadCloud, Edit3, BarChart3, Users, Settings, MoreHorizontal, UserCog } from 'lucide-react';
import { EVENTO_SESION, usuarioEnMemoria } from '@/services/api';
const items = [
  { href: '/', label: 'Resumen', icon: LayoutDashboard },
  { href: '/ingesta', label: 'Ingesta de datos', icon: UploadCloud },
  { href: '/interacciones', label: 'Interacciones', icon: MessageSquare },
  { href: '/curaduria', label: 'Curaduría', icon: Edit3 },
  { href: '/analitica', label: 'Analítica', icon: BarChart3 },
];
export default function Sidebar() {
  const pathname = usePathname();
  // Solo navegación: /usuarios y la API vuelven a exigir el rol administrador en el servidor.
  const [admin, setAdmin] = useState(false);
  useEffect(() => {
    const actualizar = () => setAdmin(usuarioEnMemoria()?.rol === 'administrador');
    const timer = setTimeout(actualizar, 0);
    window.addEventListener(EVENTO_SESION, actualizar);
    return () => { clearTimeout(timer); window.removeEventListener(EVENTO_SESION, actualizar); };
  }, []);
  return <UiTree>{<>
    <nav className="workspace-mobile" aria-label="Navegación móvil">{items.map(({href,label,icon:Icon}) => <Link key={href} href={href} aria-label={label} aria-current={pathname === href ? 'page' : undefined}><Icon size={18} /></Link>)}<Link href="/configuracion" aria-label="Configuración"><Settings size={18}/></Link></nav>
    <aside id="sidebar-principal" className="workspace-sidebar" aria-label="Menú lateral">
      <nav className="workspace-nav" aria-label="Módulos de CommunityLab">{items.map(({href,label,icon:Icon}) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined}><Icon size={15} /><span>{label}</span></Link>)}</nav>
      <div className="workspace-sidebar-bottom">
        <details className="workspace-account"><summary><span className="workspace-avatar small">CL</span><span>Mi cuenta</span><MoreHorizontal size={16}/></summary><div className="workspace-account-menu"><strong translate="no" className="notranslate">CommunityLab</strong><Link href="/equipo"><Users size={14}/>Acerca del equipo</Link>{admin && <Link href="/usuarios"><UserCog size={14}/>Usuarios del equipo</Link>}<Link href="/configuracion"><Settings size={14}/>Cuenta y seguridad</Link></div></details>
      </div>
    </aside>
  </>}</UiTree>;
}
