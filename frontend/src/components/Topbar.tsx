'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Menu } from 'lucide-react';
import Notificaciones from './Notificaciones';
import useAuthLanguage from './useAuthLanguage';
export default function Topbar() {
  const pathname = usePathname();
  const { language, t } = useAuthLanguage();
  const auth = pathname === '/login' || pathname === '/register';
  const [menuVisible, setMenuVisible] = useState(true);
  useEffect(() => {
    document.documentElement.lang = auth ? 'en' : 'es';
    document.documentElement.setAttribute('translate', 'yes');
  }, [auth]);
  if(auth) return <header className="auth-header" lang={language}><Link href="/login" className="auth-brand">Community<span className="brand-lab">Lab</span></Link><div className="auth-header-controls">{pathname === '/login' ? <button type="button" className="auth-header-login auth-header-link" onClick={() => window.dispatchEvent(new Event('communitylab-open-login'))}>{t('Iniciar sesión', 'Log in')}</button> : <Link className="auth-header-login auth-header-link" href="/login">{t('Iniciar sesión', 'Log in')}</Link>}<Link className="auth-header-link" href="/register">{t('Registrarse', 'Sign up')}</Link></div></header>;
  return <header className="workspace-topbar"><div className="workspace-brand-area"><button type="button" aria-label={menuVisible?'Ocultar menú':'Mostrar menú'} aria-expanded={menuVisible} aria-controls="sidebar-principal" onClick={()=>{setMenuVisible(!menuVisible);document.documentElement.dataset.menuOculto=String(menuVisible);}}><Menu size={17}/></button><Link href="/" className="workspace-brand">Community<span className="brand-lab">Lab</span></Link></div><Notificaciones /></header>;
}
