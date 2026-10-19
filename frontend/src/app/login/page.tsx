'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { iniciarSesion, describirError } from '@/services/api';
import { Lock, Mail, Sparkles, ArrowRight } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await iniciarSesion(email, password);
      router.push('/');
    } catch (err: unknown) {
      const info = describirError(err);
      
      // Validamos de forma segura si el error es de credenciales o no encontrado
      let mensajeFinal = info.mensaje;
      if (!mensajeFinal || mensajeFinal === 'Not Found' || info.titulo === 'Error 404') {
        mensajeFinal = 'El correo electrónico no está registrado o la contraseña es incorrecta.';
      }

      setError(mensajeFinal);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md card p-8 rounded-2xl shadow-2xl border border-border relative overflow-hidden">
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-tr from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <Sparkles className="w-5 h-5 text-white"/>
          </div>
          <span className="text-2xl font-extrabold tracking-tight text-foreground">
            Community<span className="text-cyan-400">Lab</span>
          </span>
        </div>

        <h1 className="text-xl font-bold text-center text-foreground mb-1.5">Iniciar Sesión</h1>
        <p className="text-xs text-center text-muted-foreground mb-6">
          Ingresa tus credenciales para acceder al Centro de Operaciones.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-danger-soft border border-danger/30 text-danger text-xs text-center font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              Correo Electrónico
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground"/>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operador@communitylab.com"
                className="input pl-10!"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              Contraseña
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground"/>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="input pl-10!"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2 mt-2"
          >
            <span>{loading ? 'Validando credenciales...' : 'Acceder al Sistema'}</span>
            <ArrowRight className="w-4 h-4"/>
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-muted-foreground">
          ¿No tienes una cuenta?{' '}
          <Link className="text-primary font-semibold hover:underline" href="/register">
            Regístrate aquí
          </Link>
        </div>
      </div>
    </div>
  );
}