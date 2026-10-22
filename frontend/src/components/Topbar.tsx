'use client';

import UiTree from '@/components/UiTree';
import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Menu, X } from 'lucide-react';
import Notificaciones from './Notificaciones';
import useAuthLanguage from './useAuthLanguage';
import { IDIOMAS } from '@/i18n/idioma';
const enlacesMoviles = [
  ['/', 'Resumen'], ['/ingesta', 'Ingesta de datos'], ['/interacciones', 'Interacciones'],
  ['/curaduria', 'Curaduría'], ['/analitica', 'Analítica'], ['/configuracion', 'Configuraciones'],
  ['/equipo', 'Acerca del equipo'], ['/login', 'Ver inicio de sesión'],
];
export default function Topbar() {
  const pathname = usePathname();
  const { language, t } = useAuthLanguage();
  const auth = pathname === '/login' || pathname === '/register';
  const [menuVisible, setMenuVisible] = useState(true);
  const [movilAbierto, setMovilAbierto] = useState(false);
  const menuMovil = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    document.documentElement.lang = IDIOMAS.find(i => i.valor === language)?.lang ?? 'es';
    document.documentElement.setAttribute('translate', 'yes');
  }, [language]);
  useEffect(() => {
    const alCambiarTamano = () => { if (window.innerWidth >= 768 && menuMovil.current?.open) { menuMovil.current.close(); setMovilAbierto(false); } };
    window.addEventListener('resize', alCambiarTamano);
    return () => window.removeEventListener('resize', alCambiarTamano);
  }, []);
  const cerrarMovil = () => { menuMovil.current?.close(); setMovilAbierto(false); };
  const simbolo = <Image src="/brand/communitylab-logo-current.svg" width={34} height={39} className="communitylab-symbol" alt="" aria-hidden="true" priority />;
  if (auth) return <UiTree><header className="auth-header" lang={IDIOMAS.find(i => i.valor === language)?.lang ?? 'es'}><Link href="/login" className="auth-brand notranslate" translate="no">{simbolo}Community<span className="brand-lab">Lab</span></Link><div className="auth-header-controls">{pathname === '/login' ? <button type="button" className="auth-header-login auth-header-link" onClick={() => window.dispatchEvent(new Event('communitylab-open-login'))}>{t('Iniciar sesión', 'Log in')}</button> : <Link className="auth-header-login auth-header-link" href="/login">{t('Iniciar sesión', 'Log in')}</Link>}<Link className="auth-header-link" href="/register">{t('Registrarse', 'Sign up')}</Link></div></header></UiTree>;
  return <UiTree><header className="workspace-topbar"><div className="workspace-brand-area">
    <button className="desktop-menu-toggle" type="button" aria-label={menuVisible ? 'Ocultar menú' : 'Mostrar menú'} aria-expanded={menuVisible} aria-controls="sidebar-principal" onClick={() => { setMenuVisible(!menuVisible); document.documentElement.dataset.menuOculto = String(menuVisible); }}><Menu size={17}/></button>
    <button className="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded={movilAbierto} aria-controls="menu-movil" onClick={() => { menuMovil.current?.showModal(); setMovilAbierto(true); }}><Menu size={19}/></button>
    <Link href="/" className="workspace-brand notranslate" translate="no" aria-label="CommunityLab: ir al inicio">{simbolo}</Link>
  </div><Notificaciones /></header>
  <dialog ref={menuMovil} id="menu-movil" className="mobile-menu-dialog" aria-labelledby="menu-movil-titulo" onClose={() => setMovilAbierto(false)} onClick={e => { if (e.target === e.currentTarget) cerrarMovil(); }}>
    <div className="flex items-center justify-between mb-5"><h2 id="menu-movil-titulo" className="text-lg font-bold">Menú</h2><button type="button" className="btn-ghost" aria-label="Cerrar menú" onClick={cerrarMovil}><X size={20}/></button></div>
    <nav aria-label="Todas las secciones">{enlacesMoviles.map(([href, texto]) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined} onClick={cerrarMovil}>{texto}</Link>)}</nav>
  </dialog></UiTree>;
}
