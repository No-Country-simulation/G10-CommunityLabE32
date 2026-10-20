'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Copy, KeyRound, Loader2, UserPlus, Users } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import RutaProtegida from '@/components/RutaProtegida';
import {
  actualizarUsuarioAdmin, crearUsuarioAdmin, describirError, listarUsuarios, obtenerSesion,
  type RolUsuario, type UsuarioAdmin, type UsuarioAuth,
} from '@/services/api';

const ROLES: { valor: RolUsuario; etiqueta: string }[] = [
  { valor: 'usuario', etiqueta: 'Usuario (solo métricas)' },
  { valor: 'operador', etiqueta: 'Operador' },
  { valor: 'administrador', etiqueta: 'Administrador' },
];

// Contraseña temporal generada en el navegador; se muestra una sola vez para entregarla a la persona,
// que la cambia en Configuración. No se guarda en ningún lado del frontend.
function contrasenaTemporal() {
  const alfabeto = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => alfabeto[b % alfabeto.length]).join('');
}

export default function UsuariosPage() {
  const [yo, setYo] = useState<UsuarioAuth | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState<{ texto: string; clave?: string } | null>(null);
  const [ocupado, setOcupado] = useState<number | 'nuevo' | null>(null);
  const [email, setEmail] = useState('');
  const [nombre, setNombre] = useState('');
  const [rol, setRol] = useState<RolUsuario>('operador');

  const mostrarError = (err: unknown) => { const info = describirError(err); setError(`${info.titulo}. ${info.mensaje}`); };

  useEffect(() => {
    let vigente = true;
    obtenerSesion()
      .then(async (sesion) => {
        const lista = sesion?.rol === 'administrador' ? await listarUsuarios() : [];
        if (vigente) { setYo(sesion); setUsuarios(lista); }
      })
      .catch((err) => { if (vigente) mostrarError(err); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, []);

  const crear = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(''); setAviso(null); setOcupado('nuevo');
    const clave = contrasenaTemporal();
    try {
      const creado = await crearUsuarioAdmin({ email: email.trim(), full_name: nombre.trim() || undefined, password: clave, rol });
      setUsuarios((lista) => [...lista, creado]);
      setEmail(''); setNombre('');
      setAviso({ texto: `Cuenta creada para ${creado.email}. Entrégale esta contraseña temporal por un canal privado; la cambiará en Configuración.`, clave });
    } catch (err) { mostrarError(err); }
    finally { setOcupado(null); }
  };

  const actualizar = async (usuario: UsuarioAdmin, cambios: { rol?: RolUsuario; is_active?: boolean; restablecer?: boolean }) => {
    setError(''); setAviso(null); setOcupado(usuario.id);
    const clave = cambios.restablecer ? contrasenaTemporal() : undefined;
    try {
      const actualizado = await actualizarUsuarioAdmin(usuario.id, { rol: cambios.rol, is_active: cambios.is_active, new_password: clave });
      setUsuarios((lista) => lista.map((u) => (u.id === actualizado.id ? actualizado : u)));
      setAviso(clave
        ? { texto: `Contraseña restablecida para ${actualizado.email}; sus sesiones abiertas se cerraron.`, clave }
        : { texto: `Cuenta ${actualizado.email} actualizada; sus sesiones abiertas se cerraron.` });
    } catch (err) { mostrarError(err); }
    finally { setOcupado(null); }
  };

  return (
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />
        <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-3"><Users className="w-7 h-7"/>Usuarios</h1>
            <p className="text-muted-foreground text-sm mt-1">Crea las cuentas del equipo, asigna su rol y restablece contraseñas. Solo para administradores.</p>
          </header>

          {error && <div className="mb-6 p-4 rounded-xl bg-danger-soft border border-danger/30 text-danger text-sm font-medium flex items-center gap-2.5" role="alert"><AlertCircle className="w-4 h-4 shrink-0"/><span>{error}</span></div>}
          {aviso && <div className="mb-6 p-4 rounded-xl bg-success-soft border border-success/30 text-success text-sm font-medium space-y-2" role="status">
            <p className="flex items-center gap-2.5"><CheckCircle2 className="w-4 h-4 shrink-0"/>{aviso.texto}</p>
            {aviso.clave && <p className="flex flex-wrap items-center gap-2"><code className="px-2 py-1 rounded bg-surface border border-border text-foreground font-mono select-all">{aviso.clave}</code>
              <button type="button" className="btn-secondary text-xs inline-flex items-center gap-1.5" onClick={() => void navigator.clipboard?.writeText(aviso.clave ?? '')}><Copy size={13}/>Copiar</button>
              <span className="text-xs text-muted-foreground">No se volverá a mostrar.</span></p>}
          </div>}

          {cargando ? (
            <div className="card p-12 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-primary mr-2"/><span className="text-sm text-muted-foreground">Cargando cuentas…</span></div>
          ) : yo?.rol !== 'administrador' ? (
            <div className="card p-8 text-sm text-muted-foreground">Esta sección es solo para cuentas con rol administrador.</div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-6 items-start">
              <section className="card p-0 overflow-x-auto" aria-label="Cuentas">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase tracking-wider text-subtle-foreground border-b border-border">
                    <tr><th className="p-4">Cuenta</th><th className="p-4">Rol</th><th className="p-4">Estado</th><th className="p-4 text-right">Acciones</th></tr>
                  </thead>
                  <tbody>
                    {usuarios.map((u) => {
                      const propia = u.id === yo.id;
                      return <tr key={u.id} className="border-b border-border last:border-0">
                        <td className="p-4"><p className="font-semibold text-foreground">{u.full_name || '—'}</p><p className="text-xs text-muted-foreground">{u.email}</p></td>
                        <td className="p-4">
                          <select className="input py-1.5!" aria-label={`Rol de ${u.email}`} value={u.rol} disabled={propia || ocupado !== null}
                            onChange={(e) => void actualizar(u, { rol: e.target.value as RolUsuario })}>
                            {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
                          </select>
                        </td>
                        <td className="p-4"><span className={u.is_active ? 'badge-success' : 'badge-neutral'}>{u.is_active ? 'Activa' : 'Deshabilitada'}</span></td>
                        <td className="p-4">
                          {propia ? <p className="text-xs text-muted-foreground text-right">Tu cuenta (cámbiala en Configuración)</p> :
                            <div className="flex flex-wrap justify-end gap-2">
                              <button type="button" className="btn-secondary text-xs inline-flex items-center gap-1.5" disabled={ocupado !== null}
                                onClick={() => { if (window.confirm(`¿Generar una contraseña temporal nueva para ${u.email}?`)) void actualizar(u, { restablecer: true }); }}>
                                {ocupado === u.id ? <Loader2 size={13} className="animate-spin"/> : <KeyRound size={13}/>}Restablecer contraseña
                              </button>
                              <button type="button" className="btn-secondary text-xs" disabled={ocupado !== null}
                                onClick={() => void actualizar(u, { is_active: !u.is_active })}>{u.is_active ? 'Deshabilitar' : 'Habilitar'}</button>
                            </div>}
                        </td>
                      </tr>;
                    })}
                  </tbody>
                </table>
              </section>

              <form onSubmit={crear} className="card p-6 space-y-4" aria-labelledby="nueva-cuenta">
                <h2 id="nueva-cuenta" className="text-base font-bold text-foreground flex items-center gap-2"><UserPlus size={17}/>Nueva cuenta</h2>
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Correo electrónico
                  <input className="input mt-1.5" type="email" required autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="persona@equipo.com"/></label>
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Nombre (opcional)
                  <input className="input mt-1.5" maxLength={255} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre y apellido"/></label>
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Rol
                  <select className="input mt-1.5" value={rol} onChange={(e) => setRol(e.target.value as RolUsuario)}>
                    {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
                  </select></label>
                <p className="text-xs text-muted-foreground">Se genera una contraseña temporal aleatoria que verás una sola vez.</p>
                <button type="submit" className="btn-primary w-full inline-flex items-center justify-center gap-2" disabled={ocupado !== null}>
                  {ocupado === 'nuevo' ? <Loader2 size={14} className="animate-spin"/> : <UserPlus size={14}/>}Crear cuenta
                </button>
              </form>
            </div>
          )}
        </main>
      </div>
    </RutaProtegida>
  );
}
