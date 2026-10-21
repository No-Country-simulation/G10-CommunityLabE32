'use client';


import UiTree from '@/components/UiTree';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  obtenerPerfilActual,
  actualizarPerfilUsuario,
  describirError,
  UsuarioAuth,
  cerrarSesion,
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
  LogOut,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import PasswordInput from '@/components/PasswordInput';
import RutaProtegida from '@/components/RutaProtegida';
import TokenOperador from '@/components/TokenOperador';

export default function ConfiguracionPage() {
  const router = useRouter();
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
      const actualizado = await actualizarPerfilUsuario({
        full_name: fullName,
        email,
      });
      setUsuario(actualizado);
      setMensajeExito('Tus datos se actualizaron correctamente.');
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
      setMensajeExito('Tu contraseña se actualizó correctamente.');
    } catch (err) {
      setMensajeError(describirError(err).mensaje || 'Error al actualizar la contraseña.');
    } finally {
      setGuardandoClave(false);
    }
  };

  const aplicarTema = (nuevo: 'light' | 'dark') => {
    document.documentElement.dataset.theme = nuevo;
    try {
      localStorage.setItem('communitylab-theme', nuevo);
    } catch {}
  };

  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Configuración de la cuenta y seguridad
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Actualiza tus datos, protege tu cuenta y personaliza la apariencia.
            </p>
          </header>

          {mensajeExito && (
            <div className="mb-6 p-4 rounded-xl bg-success-soft border border-success/30 text-success text-sm font-medium flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{mensajeExito}</span>
            </div>
          )}

          {mensajeError && (
            <div className="mb-6 p-4 rounded-xl bg-danger-soft border border-danger/30 text-danger text-sm font-medium flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{mensajeError}</span>
            </div>
          )}

          {cargandoPerfil ? (
            <div className="card p-12 flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-primary mr-2" />
              <span className="text-sm text-muted-foreground">Cargando tu perfil…</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Tarjeta 1: Información del Perfil y Correo */}
              <form onSubmit={guardarDatosPersonales} className="card p-6 flex flex-col justify-between space-y-5">
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-border pb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-primary-soft text-primary flex items-center justify-center font-bold">
                        <User className="w-5 h-5" />
                      </div>
                      <div>
                        <h2 className="text-base font-bold text-foreground">Tu perfil</h2>
                        <p className="text-xs text-muted-foreground">
                          {usuario ? `ID #${usuario.id} · Sesión autenticada` : 'Vista local · sin sesión de cuenta'}
                        </p>
                      </div>
                    </div>
                    <span className={usuario ? "badge-success" : "badge-neutral"}>{usuario ? 'Sesión activa' : 'Vista local'}</span>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Nombre completo
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
                      Correo electrónico de acceso
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
                  disabled={guardandoPerfil || !usuario}
                  className="btn-primary w-full flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Save className="w-4 h-4" />
                  <span>{guardandoPerfil ? 'Guardando cambios…' : 'Actualizar datos del perfil'}</span>
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
                      <h2 className="text-base font-bold text-foreground">Seguridad y contraseña</h2>
                      <p className="text-xs text-muted-foreground">
                        Elige una contraseña de al menos 10 caracteres.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Contraseña actual
                    </label>
                    <PasswordInput
                      aria-label="Contraseña actual" autoComplete="current-password"
                      required
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="input"
                      placeholder="Ingresa tu contraseña actual"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Nueva contraseña
                    </label>
                    <PasswordInput
                      aria-label="Nueva contraseña" autoComplete="new-password"
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
                      Confirmar nueva contraseña
                    </label>
                    <PasswordInput
                      aria-label="Confirmar nueva contraseña" autoComplete="new-password"
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
                  disabled={guardandoClave || !usuario}
                  className="btn-secondary w-full flex items-center justify-center gap-2 cursor-pointer"
                >
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  <span>{guardandoClave ? 'Actualizando clave…' : 'Cambiar contraseña'}</span>
                </button>
              </form>

              {/* Tarjeta 3: Token de Operador (Compatibilidad Híbrida Backend) */}
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
                  Para procesar pendientes, aprobar textos, generar banners e importar el historial se requiere el rol de operador. Los permisos se verifican en el servidor según la sesión de la cuenta.
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
                      <h2 className="text-base font-bold text-foreground">Apariencia e interfaz</h2>
                      <p className="text-xs text-muted-foreground">
                        Personaliza el tema visual de tu estación de trabajo.
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
                    El modo oscuro usa fondo negro y paneles grises. Puedes cambiar el tema aquí; tu preferencia se guarda en este navegador.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => aplicarTema('light')}
                    className="btn-secondary justify-center cursor-pointer"
                  >
                    Modo claro
                  </button>
                  <button
                    type="button"
                    onClick={() => aplicarTema('dark')}
                    className="btn-secondary justify-center cursor-pointer"
                  >
                    Modo oscuro
                  </button>
                </div>
              </div>
            </div>
          )}
          <section className="card mt-6 p-6 flex flex-wrap items-center justify-between gap-4" aria-labelledby="sesion-titulo">
            <div>
              <h2 id="sesion-titulo" className="text-base font-bold text-foreground">Sesión</h2>
              <p className="text-sm text-muted-foreground mt-1">Sal de tu cuenta en este dispositivo.</p>
            </div>
            <button
              type="button"
              onClick={() => { cerrarSesion(); router.push('/login'); }}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-danger/30 bg-danger-soft px-5 py-3 text-sm font-semibold text-danger hover:bg-danger hover:text-white transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Cerrar sesión
            </button>
          </section>
        </main>
      </div>
    </RutaProtegida>
  )}</UiTree>;
}
