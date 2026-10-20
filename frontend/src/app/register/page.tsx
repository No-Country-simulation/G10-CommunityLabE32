'use client';
import { useState } from 'react';
import Link from 'next/link';
import useAuthLanguage from '@/components/useAuthLanguage';
import { registrarUsuario, describirError } from '@/services/api';
import { CheckCircle2, Loader2 } from 'lucide-react';
export default function RegisterPage() {
  const { language, t } = useAuthLanguage();
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [exito, setExito] = useState(false);
  const [loading, setLoading] = useState(false);
  const registrar = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setLoading(true);
    try { await registrarUsuario(nombre, email, password); setExito(true); }
    catch (err) { setError(language === 'en' ? 'Unable to create your account. Check your details and try again.' : describirError(err).mensaje || 'No se pudo crear la cuenta.'); }
    finally { setLoading(false); }
  };
  return <main className="auth-page" lang={language}><div className="auth-content"><h1>{t('Crea tu cuenta en CommunityLab', 'Create your CommunityLab account')}</h1>
    {exito ? <div className="auth-success"><CheckCircle2 size={24} /><h2>{t('Tu cuenta está lista', 'Your account is ready')}</h2><p>{t('Ya puedes iniciar sesión con tu correo electrónico y contraseña.', 'You can now log in with your email and password.')}</p><Link className="auth-submit" href="/login">{t('Ir al inicio de sesión', 'Log in')}</Link></div> : <form className="auth-form" onSubmit={registrar}>
      <label htmlFor="register-name" className="sr-only">{t('Nombre completo', 'Full name')}</label><input className="auth-input" id="register-name" placeholder={t('Nombre completo', 'Full name')} autoComplete="name" required value={nombre} onChange={e => setNombre(e.target.value)} />
      <label htmlFor="register-email" className="sr-only">{t('Correo electrónico', 'Email address')}</label><input className="auth-input" id="register-email" placeholder={t('Correo electrónico', 'Email address')} type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
      <label htmlFor="register-password" className="sr-only">{t('Contraseña', 'Password')}</label><input className="auth-input" id="register-password" placeholder={t('Contraseña (mínimo 6 caracteres)', 'Password (at least 6 characters)')} type="password" autoComplete="new-password" minLength={6} required value={password} onChange={e => setPassword(e.target.value)} />
      {error && <p role="alert" className="auth-error">{error}</p>}<button className="auth-submit" type="submit" disabled={loading}>{loading ? <><Loader2 size={16} className="animate-spin" /> {t('Creando cuenta…', 'Creating account…')}</> : t('Crear cuenta', 'Create account')}</button>
    </form>}
    <p className="auth-signup">{t('¿Ya tienes una cuenta?', 'Already have an account?')} <Link href="/login">{t('Inicia sesión', 'Log in')}</Link></p>
  </div><footer className="auth-footer">CommunityLab <span>·</span> {t('Inteligencia para tu comunidad', 'Insights for your community')}</footer></main>;
}
