'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { registrarUsuario, describirError } from '@/services/api';
import { Lock, Mail, User, Sparkles, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [exito, setExito] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await registrarUsuario(fullName, email, password);
      setExito(true);
      // Redirigimos al usuario al login después de 2 segundos de mostrar el éxito
      setTimeout(() => {
        router.push('/login');
      }, 2000);
    } catch (err: unknown) {
      const info = describirError(err);
      setError(info.mensaje || 'No se pudo completar el registro. El correo podría ya estar registrado.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="w-full max-w-md card p-8 rounded-2xl shadow-2xl border border-border relative overflow-hidden">
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-tr from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <Sparkles className="w-5 h-5 text-white"/>
          </div>
          <span className="text-2xl font-extrabold tracking-tight text-foreground">
            Community<span className="text-cyan-400">Lab</span>
          </span>
        </div>

        <h1 className="text-xl font-bold text-center text-foreground mb-1.5">Crear Cuenta de Operador</h1>
        <p className="text-xs text-center text-muted-foreground mb-6">
          Regístrate para obtener acceso seguro con token JWT a la plataforma.
        </p>

        {exito && (
          <div className="mb-4 p-3 rounded-xl bg-success-soft border border-success/30 text-success text-xs text-center font-medium flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>¡Registro exitoso! Por favor inicia sesión.</span>
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-danger-soft border border-danger/30 text-danger text-xs text-center font-medium">
            {error}
          </div>
        )}

        {!exito && (
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                Nombre Completo
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground"/>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nombre y Apellido"
                  className="input pl-10!"
                />
              </div>
            </div>

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
                Contraseña Segura
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground"/>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 6 caracteres"
                  className="input pl-10!"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 mt-2 cursor-pointer"
            >
              <span>{loading ? 'Creando cuenta...' : 'Completar Registro'}</span>
              <ArrowRight className="w-4 h-4"/>
            </button>
          </form>
        )}

        <div className="mt-6 text-center text-xs text-muted-foreground">
          ¿Ya tienes una cuenta?{' '}
          <Link className="text-primary font-semibold hover:underline" href="/login">
            Inicia sesión aquí
          </Link>
        </div>
      </div>
    </div>
  );
}