'use client';

import { useEffect, useState } from 'react';
import {
  obtenerPerfilActual,
  actualizarPerfilUsuario,
  describirError,
  UsuarioAuth,
} from '@/services/api';
import {
  User,
  Mail,
  Lock,
  ShieldCheck,
  Save,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Palette,
  KeyRound,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import RutaProtegida from '@/components/RutaProtegida';
import TokenOperador from '@/components/TokenOperador';

export default function ConfiguracionPage() {
  const [usuario, setUsuario] = useState<UsuarioAuth | null>(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [cargandoPerfil, setCargandoPerfil] = useState(true);
  const [guardandoPerfil, setGuardandoPerfil] = useState(false);
  const [guardandoClave, setGuardandoClave] = useState(false);

  const [mensajeExito, setMensajeExito] = useState<string | null>(null);
  const [mensajeError, setMensajeError] = useState<string | null>(null);

  useEffect(() => {
    obtenerPerfilActual()
      .then((u) => {
        setUsuario(u);
        setFullName(u.full_name ?? '');
        setEmail(u.email);
        setCargandoPerfil(false);
      })
      .catch(() => {
        setCargandoPerfil(false);
      });
  }, []);

  const guardarDatosPersonales = async (e: React.FormEvent) => {
    e.preventDefault();
    setMensajeExito(null);
    setMensajeError(null);
    setGuardandoPerfil(true);

    try {
      // Cambiar el correo exige la contraseña actual (se toma de la tarjeta de Seguridad).
      const cambiaEmail = email.trim().toLowerCase() !== (usuario?.email ?? '');
      if (cambiaEmail && !currentPassword) {
        setMensajeError('Para cambiar el correo escribe tu contraseña actual en la tarjeta de contraseña.');
        return;
      }
      const actualizado = await actualizarPerfilUsuario({
        full_name: fullName,
        ...(cambiaEmail ? { email, current_password: currentPassword } : {}),
      });
      setUsuario(actualizado);
      setMensajeExito('Tus datos de perfil se actualizaron correctamente en la base de datos.');
    } catch (err) {
      setMensajeError(describirError(err).mensaje || 'No se pudo actualizar el perfil.');
    } finally {
      setGuardandoPerfil(false);
    }
  };

  const cambiarContrasena = async (e: React.FormEvent) => {
    e.preventDefault();
    setMensajeExito(null);
    setMensajeError(null);

    if (newPassword !== confirmPassword) {
      setMensajeError('La nueva contraseña y su confirmación no coinciden.');
      return;
    }

    setGuardandoClave(true);
    try {
      await actualizarPerfilUsuario({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setMensajeExito('Contraseña actualizada. Se cerraron tus otras sesiones abiertas.');
    } catch (err) {
      setMensajeError(describirError(err).mensaje || 'Error al actualizar la contraseña.');
    } finally {
      setGuardandoClave(false);
    }
  };

  const aplicarTema = (nuevo: 'light' | 'dark') => {
    document.documentElement.dataset.theme = nuevo;
    try {
      localStorage.setItem('theme', nuevo);
    } catch {}
  };

  return (
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Configuración de Cuenta y Seguridad
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Administra tus credenciales de operador, actualiza tu correo o contraseña y gestiona tus permisos.
            </p>
          </header>

          {mensajeExito && (
            <div className="mb-6 p-4 rounded-xl bg-success-soft border border-success/30 text-success text-sm font-medium flex items-center gap-2.5 max-w-4xl">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{mensajeExito}</span>
            </div>
          )}

          {mensajeError && (
            <div className="mb-6 p-4 rounded-xl bg-danger-soft border border-danger/30 text-danger text-sm font-medium flex items-center gap-2.5 max-w-4xl">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{mensajeError}</span>
            </div>
          )}

          {cargandoPerfil ? (
            <div className="card p-12 flex items-center justify-center max-w-4xl">
              <Loader2 className="w-5 h-5 animate-spin text-primary mr-2" />
              <span className="text-sm text-muted-foreground">Cargando perfil del operador…</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl">
              {/* Tarjeta 1: Información del Perfil y Correo */}
              <form onSubmit={guardarDatosPersonales} className="card p-6 flex flex-col justify-between space-y-5">
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-border pb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-primary-soft text-primary flex items-center justify-center font-bold">
                        <User className="w-5 h-5" />
                      </div>
                      <div>
                        <h2 className="text-base font-bold text-foreground">Perfil del Operador</h2>
                        <p className="text-xs text-muted-foreground">
                          ID #{usuario?.id ?? '—'} · Rol: {usuario?.rol ?? '—'}
                        </p>
                      </div>
                    </div>
                    <span className="badge-success">Verificado</span>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Nombre Completo
                    </label>
                    <div className="relative">
                      <User className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground" />
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        className="input pl-10!"
                        placeholder="Tu nombre completo"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Correo Electrónico de Acceso
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-3 w-4 h-4 text-subtle-foreground" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="input pl-10!"
                        placeholder="operador@communitylab.com"
                      />
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={guardandoPerfil}
                  className="btn-primary w-full flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Save className="w-4 h-4" />
                  <span>{guardandoPerfil ? 'Guardando cambios…' : 'Actualizar Datos de Perfil'}</span>
                </button>
              </form>

              {/* Tarjeta 2: Cambio de Contraseña */}
              <form onSubmit={cambiarContrasena} className="card p-6 flex flex-col justify-between space-y-5">
                <div className="space-y-4">
                  <div className="flex items-center gap-3 border-b border-border pb-4">
                    <div className="w-10 h-10 rounded-xl bg-info-soft text-info flex items-center justify-center">
                      <Lock className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-foreground">Seguridad y Contraseña</h2>
                      <p className="text-xs text-muted-foreground">
                        Almacenamiento seguro con hash Bcrypt en PostgreSQL
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Contraseña Actual
                    </label>
                    <input
                      type="password"
                      required
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="input"
                      placeholder="Ingresa tu contraseña actual"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Nueva Contraseña
                    </label>
                    <input
                      type="password"
                      required
                      minLength={10}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="input"
                      placeholder="Mínimo 10 caracteres"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Confirmar Nueva Contraseña
                    </label>
                    <input
                      type="password"
                      required
                      minLength={10}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="input"
                      placeholder="Repite la nueva contraseña"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={guardandoClave}
                  className="btn-secondary w-full flex items-center justify-center gap-2 cursor-pointer"
                >
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  <span>{guardandoClave ? 'Actualizando clave…' : 'Cambiar Contraseña'}</span>
                </button>
              </form>

              {/* Tarjeta 3: Permisos de la cuenta */}
              <div className="card p-6 space-y-4">
                <div className="flex items-center gap-3 border-b border-border pb-4">
                  <div className="w-10 h-10 rounded-xl bg-warning-soft text-warning flex items-center justify-center">
                    <KeyRound className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-foreground">Permisos de la cuenta</h2>
                    <p className="text-xs text-muted-foreground">
                      Rol asignado por un administrador
                    </p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Procesar pendientes, aprobar textos, generar banners e importar historial requieren el rol operador. El navegador no usa tokens de operador: los permisos dependen de tu sesión.
                </p>
                <TokenOperador />
              </div>

              {/* Tarjeta 4: Preferencias de Apariencia */}
              <div className="card p-6 space-y-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-3 border-b border-border pb-4">
                    <div className="w-10 h-10 rounded-xl bg-primary-soft text-primary flex items-center justify-center">
                      <Palette className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-foreground">Apariencia e Interfaz</h2>
                      <p className="text-xs text-muted-foreground">
                        Personaliza el tema visual de tu estación de trabajo
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
                    Elige entre el modo claro de alto contraste editorial o el modo oscuro inspirado en centros de monitoreo nocturno.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => aplicarTema('light')}
                    className="btn-secondary justify-center cursor-pointer"
                  >
                    Modo Claro
                  </button>
                  <button
                    type="button"
                    onClick={() => aplicarTema('dark')}
                    className="btn-secondary justify-center cursor-pointer"
                  >
                    Modo Oscuro
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </RutaProtegida>
  );
}