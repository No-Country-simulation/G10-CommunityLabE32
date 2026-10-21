'use client';

import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Menu } from 'lucide-react';
import Notificaciones from './Notificaciones';
import useAuthLanguage from './useAuthLanguage';
export default function Topbar() {
  const pathname = usePathname();
  const { language, t } = useAuthLanguage();
  const auth = pathname === '/login' || pathname === '/register';
  const [menuVisible, setMenuVisible] = useState(true);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.setAttribute('translate', 'yes');
  }, [language]);
  if(auth) return <UiTree>{<header className="auth-header" lang={language}><Link href="/login" className="auth-brand notranslate" translate="no"><Image src="/brand/communitylab-logo-current.svg" width={34} height={39} className="communitylab-symbol" alt="" aria-hidden="true" />Community<span className="brand-lab">Lab</span></Link><div className="auth-header-controls">{pathname === '/login' ? <button type="button" className="auth-header-login auth-header-link" onClick={() => window.dispatchEvent(new Event('communitylab-open-login'))}>{t('Iniciar sesión', 'Log in')}</button> : <Link className="auth-header-login auth-header-link" href="/login">{t('Iniciar sesión', 'Log in')}</Link>}<Link className="auth-header-link" href="/register">{t('Registrarse', 'Sign up')}</Link></div></header>}</UiTree>;
  return <UiTree>{<header className="workspace-topbar"><div className="workspace-brand-area"><button type="button" aria-label={menuVisible?'Ocultar menú':'Mostrar menú'} aria-expanded={menuVisible} aria-controls="sidebar-principal" onClick={()=>{setMenuVisible(!menuVisible);document.documentElement.dataset.menuOculto=String(menuVisible);}}><Menu size={17}/></button><Link href="/" className="workspace-brand notranslate" translate="no"><Image src="/brand/communitylab-logo-current.svg" width={34} height={39} className="communitylab-symbol" alt="" aria-hidden="true" />Community<span className="brand-lab">Lab</span></Link></div><Notificaciones /></header>}</UiTree>;
}
