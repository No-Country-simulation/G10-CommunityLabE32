'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import useAuthLanguage from '@/components/useAuthLanguage';
import { iniciarSesion, describirError } from '@/services/api';
import { esVistaLocal } from '@/services/vistaLocal';
import { ArrowLeft, ArrowRight, Eye, EyeOff, Loader2, Monitor, MessageSquare, FileText, Check } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { language, t } = useAuthLanguage();
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const open = () => dialogRef.current?.showModal();
    window.addEventListener('communitylab-open-login', open);
    return () => window.removeEventListener('communitylab-open-login', open);
  }, []);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [paso, setPaso] = useState<'correo' | 'clave'>('correo');
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [local, setLocal] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setLocal(esVistaLocal()), 0);
    return () => clearTimeout(timer);
  }, []);
  const continuar = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    if (paso === 'correo') { setPaso('clave'); return; }
    setLoading(true);
    try { await iniciarSesion(email, password); router.push('/'); }
    catch (err) { setError(language === 'en' ? 'Unable to log in. Check your credentials and connection.' : describirError(err).mensaje || 'No se pudo iniciar sesión. Revisa tus credenciales y la conexión.'); }
    finally { setLoading(false); }
  };
  return (
    <main className="auth-page login-illustrated login-centered" lang={language}>
      <div className="login-layout">
        <section className="login-art-panel" aria-labelledby="login-art-title">
          <span className="login-art-label">{t('Equipo 32', 'Team 32')}</span>
          <h2 id="login-art-title">{t('Las buenas ideas', 'Great ideas')}<br/>{t('crecen en comunidad.', 'grow together.')}</h2>
          <div className="login-conversation-art" aria-hidden="true">
            <div className="login-chat-card"><MessageSquare size={28}/><span>{t('Todo empieza con', 'It all starts with')}<br/>{t('una conversación.', 'a conversation.')}</span><div className="login-chat-lines"><i/><i/><i/></div></div>
            <div className="login-story-card"><FileText size={25}/><span>{t('Una idea.', 'One idea.')}<br/>{t('Muchas posibilidades.', 'Endless possibilities.')}</span><div className="login-story-status"><Check size={14}/> {t('En comunidad', 'Together')}</div></div>
          </div>
          <p>{t('Conversaciones que inspiran.', 'Conversations that inspire.')}<br/>{t('Historias que conectan.', 'Stories that connect.')}</p>
        </section>
      <dialog ref={dialogRef} className="login-dialog" aria-labelledby="login-form-title" onClick={event => { if (event.target === event.currentTarget) dialogRef.current?.close(); }}>
      <div className="auth-content">
        <button type="button" className="login-dialog-close" onClick={() => dialogRef.current?.close()} aria-label={t('Cerrar', 'Close')}>×</button>
        <h1 id="login-form-title">{t('Inicia sesión en CommunityLab', 'Log in to CommunityLab')}</h1>
        <form onSubmit={continuar} className="auth-form">
          {paso === 'correo' ? <><label htmlFor="login-email" className="sr-only">{t('Correo electrónico', 'Email address')}</label><input id="login-email" className="auth-input" type="email" autoComplete="email" placeholder={t('Correo electrónico', 'Email address')} required value={email} onChange={e => setEmail(e.target.value)} /></> : <>
            <button className="auth-email-back" type="button" onClick={() => { setPaso('correo'); setError(''); }}><ArrowLeft size={14} />{email}</button>
            <div className="auth-password"><label htmlFor="login-password" className="sr-only">{t('Contraseña', 'Password')}</label><input id="login-password" className="auth-input" type={visible ? 'text' : 'password'} autoComplete="current-password" placeholder={t('Contraseña', 'Password')} required autoFocus value={password} onChange={e => setPassword(e.target.value)} /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? t('Ocultar contraseña', 'Hide password') : t('Mostrar contraseña', 'Show password')}>{visible ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>
          </>}
          {error && <p role="alert" className="auth-error">{error}</p>}
          <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><Loader2 size={16} className="animate-spin" /> {t('Iniciando sesión…', 'Logging in…')}</> : paso === 'correo' ? t('Continuar con correo', 'Continue with email') : t('Iniciar sesión', 'Log in')}</button>
        </form>
        {local && <><div className="auth-divider"><span>{t('o', 'or')}</span></div><Link href="/" className="auth-option"><Monitor size={16} /> {t('Explorar en localhost', 'Explore on localhost')} <ArrowRight size={14} /></Link><p className="auth-local-note">{t('Vista previa sin registro. Conecta el backend para cargar los datos.', 'Preview without signing up. Connect the backend to load data.')}</p></>}
        <p className="auth-signup">{t('¿No tienes una cuenta?', 'Don’t have an account?')} <Link href="/register">{t('Regístrate', 'Sign up')}</Link></p>
      </div>
      </dialog>
      </div>
      <footer className="auth-footer">CommunityLab <span>·</span> {t('Inteligencia para tu comunidad', 'Insights for your community')}</footer>
    </main>
  );
}
