'use client';

import UiTree from '@/components/UiTree';
import { useCallback, useEffect, useState } from 'react';
import { Database, EyeOff, Eye, Trash2, RefreshCw, Loader2, AlertTriangle } from 'lucide-react';
import {
  EVENTO_SESION, usuarioEnMemoria, describirError, listarLotesCargados, cambiarVisibilidadLotes,
  previsualizarEliminacion, eliminarLotes, type LoteCargado, type PlanEliminacion,
} from '@/services/api';

// Lotes cargados en CommunityLab: ocultarlos del panel (reversible) o eliminarlos (irreversible).
// Solo se muestra a administradores; la API vuelve a exigir el rol en cada petición.
const claveDe = (l: LoteCargado) => `${l.fuente_ingesta}|${l.origen}|${l.periodo}`;
const fecha = (valor: string | null) => valor ? new Date(valor).toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' }) : 'Sin fecha';

export default function DatosCargados() {
  const [admin, setAdmin] = useState(false);
  const [lotes, setLotes] = useState<LoteCargado[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [ocupado, setOcupado] = useState(false);
  const [plan, setPlan] = useState<PlanEliminacion | null>(null);
  const [confirmacion, setConfirmacion] = useState('');
  const [incluirAprobados, setIncluirAprobados] = useState(false);

  useEffect(() => {
    const actualizar = () => setAdmin(usuarioEnMemoria()?.rol === 'administrador');
    const timer = setTimeout(actualizar, 0);
    window.addEventListener(EVENTO_SESION, actualizar);
    return () => { clearTimeout(timer); window.removeEventListener(EVENTO_SESION, actualizar); };
  }, []);

  const cargar = useCallback(async () => {
    setCargando(true); setError('');
    try {
      const items = await listarLotesCargados();
      setLotes(items);
      setMarcados(actual => new Set([...actual].filter(k => items.some(l => claveDe(l) === k))));
    } catch (e) { setError(describirError(e).mensaje); }
    finally { setCargando(false); }
  }, []);

  useEffect(() => {
    if (!admin) return;
    const timer = setTimeout(() => { void cargar(); }, 0);
    return () => clearTimeout(timer);
  }, [admin, cargar]);

  if (!admin) return null;

  const seleccion = lotes.filter(l => marcados.has(claveDe(l)));
  const alternar = (l: LoteCargado) => {
    setPlan(null); setAviso('');
    setMarcados(actual => { const nuevo = new Set(actual); if (nuevo.has(claveDe(l))) nuevo.delete(claveDe(l)); else nuevo.add(claveDe(l)); return nuevo; });
  };
  const terminar = async (mensaje: string) => {
    setAviso(mensaje); setPlan(null); setConfirmacion(''); setIncluirAprobados(false); setMarcados(new Set());
    window.dispatchEvent(new Event('communitylab-curaduria-cambio'));
    await cargar();
  };
  const visibilidad = async (oculto: boolean) => {
    setOcupado(true); setError('');
    try {
      await cambiarVisibilidadLotes(seleccion, oculto);
      await terminar(oculto ? `${seleccion.length} lote(s) ocultos del panel. Puedes volver a mostrarlos cuando quieras.` : `${seleccion.length} lote(s) visibles de nuevo en el panel.`);
    } catch (e) { setError(describirError(e).mensaje); }
    finally { setOcupado(false); }
  };
  const prever = async () => {
    setOcupado(true); setError(''); setAviso('');
    try { setPlan(await previsualizarEliminacion(seleccion)); setConfirmacion(''); setIncluirAprobados(false); }
    catch (e) { setError(describirError(e).mensaje); }
    finally { setOcupado(false); }
  };
  const eliminar = async () => {
    setOcupado(true); setError('');
    try {
      const hecho = await eliminarLotes(seleccion, incluirAprobados);
      await terminar(`Eliminados ${hecho.lotes} lote(s): ${hecho.mensajes} mensaje(s) y ${hecho.activos} contenido(s).`);
    } catch (e) { setError(describirError(e).mensaje); }
    finally { setOcupado(false); }
  };
  const puedeEliminar = plan !== null && confirmacion === 'ELIMINAR' && plan.en_proceso === 0 && (plan.aprobados === 0 || incluirAprobados);

  return <UiTree>{(
    <section className="ingestion-datos card p-5 sm:p-6 min-w-0" aria-labelledby="datos-cargados-titulo" aria-busy={cargando || ocupado}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 id="datos-cargados-titulo" className="text-[15px] font-semibold text-foreground flex items-center gap-2"><Database className="w-4 h-4 shrink-0 text-[#90a8ed]" aria-hidden="true" />Datos cargados</h2>
          <p className="text-sm text-muted-foreground mt-1">Lotes que hay en CommunityLab, por vía de entrada. Oculta los de prueba o elimínalos para empezar con datos limpios.</p>
        </div>
        <button type="button" className="btn-secondary" onClick={() => void cargar()} disabled={cargando || ocupado}><RefreshCw size={14} aria-hidden="true" />Actualizar</button>
      </div>

      {error && <p role="alert" className="card p-3 mb-3 text-sm">{error}</p>}
      {aviso && <p role="status" className="card p-3 mb-3 text-sm">{aviso}</p>}

      {cargando && lotes.length === 0 ? <div className="flex justify-center p-6"><Loader2 className="w-5 h-5 animate-spin" aria-label="Cargando lotes" /></div>
        : lotes.length === 0 ? <p className="text-sm text-muted-foreground p-4">No hay lotes cargados.</p>
        : <ul className="datos-lotes" aria-label="Lotes cargados">
          {lotes.map((l, indice) => {
            const id = `datos-lote-${indice}`;
            return <li key={claveDe(l)} className={`datos-lote ${l.oculto ? 'is-oculto' : ''}`}>
              <input id={id} type="checkbox" checked={marcados.has(claveDe(l))} onChange={() => alternar(l)} disabled={ocupado} />
              <label htmlFor={id} className="min-w-0">
                <strong translate="no">{l.origen} · {l.periodo}</strong>
                <span className="block text-xs text-muted-foreground mt-1">Última actualización: {fecha(l.ultimo)}</span>
              </label>
              <span className="badge-neutral">{l.fuente_ingesta === 'discord' ? 'Discord' : 'Carga manual'}</span>
              <span className="text-sm tabular-nums">{l.mensajes} mensaje(s){l.mensajes_compartidos > 0 && <span className="block text-xs text-muted-foreground">{l.mensajes_compartidos} también en otro lote</span>}</span>
              <span className="text-sm tabular-nums">{l.activos} contenido(s){l.aprobados > 0 && <span className="block text-xs text-muted-foreground">{l.aprobados} aprobado(s)</span>}</span>
              <span className="text-xs">{l.en_proceso > 0 ? <span className="badge-neutral">En proceso</span> : l.oculto ? <span className="badge-neutral">Oculto</span> : <span className="badge-neutral">Visible</span>}</span>
            </li>;
          })}
        </ul>}

      <div className="flex flex-wrap gap-2 mt-4">
        <button type="button" className="btn-secondary" disabled={!seleccion.length || ocupado} onClick={() => void visibilidad(true)}><EyeOff size={14} aria-hidden="true" />Ocultar del panel</button>
        <button type="button" className="btn-secondary" disabled={!seleccion.length || ocupado} onClick={() => void visibilidad(false)}><Eye size={14} aria-hidden="true" />Mostrar en el panel</button>
        <button type="button" className="btn-danger-soft" disabled={!seleccion.length || ocupado} onClick={() => void prever()}><Trash2 size={14} aria-hidden="true" />Eliminar…</button>
        {seleccion.length > 0 && <span className="text-xs text-muted-foreground self-center">{seleccion.length} lote(s) seleccionado(s)</span>}
      </div>

      {plan && <div role="region" aria-label="Confirmar eliminación" className="datos-confirmacion mt-4 p-4">
        <p className="font-semibold flex items-center gap-2"><AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />Esto no se puede deshacer</p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-sm">
          <li>Se borrarán {plan.mensajes} mensaje(s){plan.mensajes_conservados > 0 && `; ${plan.mensajes_conservados} se conservan porque otro lote también los usa`}.</li>
          <li>Se borrarán {plan.activos} contenido(s) de Curaduría con su historial y {plan.banners} banner(s).</li>
          <li>Las copias ya guardadas en OCI y el historial importado de Discord no se tocan.</li>
        </ul>
        {plan.en_proceso > 0 && <p role="alert" className="text-sm mt-3">Hay {plan.en_proceso} trabajo(s) en proceso: espera a que terminen.</p>}
        {plan.aprobados > 0 && <label className="flex items-center gap-2 text-sm mt-3"><input type="checkbox" checked={incluirAprobados} onChange={e => setIncluirAprobados(e.target.checked)} />Incluir {plan.aprobados} contenido(s) ya aprobado(s)</label>}
        <label htmlFor="datos-confirmar" className="block text-sm mt-3">Escribe <strong>ELIMINAR</strong> para confirmar</label>
        <input id="datos-confirmar" className="input mt-1 max-w-xs" value={confirmacion} onChange={e => setConfirmacion(e.target.value)} autoComplete="off" spellCheck={false} />
        <div className="flex flex-wrap gap-2 mt-3">
          <button type="button" className="btn-secondary" onClick={() => setPlan(null)} disabled={ocupado}>Cancelar</button>
          <button type="button" className="btn-danger-soft" onClick={() => void eliminar()} disabled={!puedeEliminar || ocupado}>{ocupado ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Trash2 size={14} aria-hidden="true" />}Eliminar definitivamente</button>
        </div>
      </div>}
    </section>
  )}</UiTree>;
}
