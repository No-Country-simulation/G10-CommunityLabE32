'use client';


import UiTree from '@/components/UiTree';
import EnviarAnalisisDiscord from './EnviarAnalisisDiscord';
import { useCallback, useEffect, useRef, useState } from 'react';
import { CalendarDays, Hash, Loader2, ArrowRight, CheckCircle2, AlertCircle, ChevronDown } from 'lucide-react';
import { previsualizarDiscordHistorico, crearImportacionDiscord, consultarImportacionDiscord, obtenerEscuchaDiscord, cambiarEscuchaDiscord, type EstadoEscuchaDiscord, describirError, type PrevisualizacionDiscord, type ImportacionDiscord } from '@/services/api';

type Unidad = 'dias' | 'meses' | 'anos';
function rangoFechas(unidad: Unidad, desde: string, hasta: string) {
  if (!desde || !hasta) throw new Error('Selecciona el inicio y el final del período.');
  let inicio = desde;
  let fin = hasta;
  if (unidad === 'meses') {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(desde) || !/^\d{4}-(0[1-9]|1[0-2])$/.test(hasta)) throw new Error('Selecciona meses válidos.');
    inicio = `${desde}-01`;
    const [ano, mes] = hasta.split('-').map(Number);
    fin = `${hasta}-${new Date(Date.UTC(ano, mes, 0)).getUTCDate()}`;
  } else if (unidad === 'anos') {
    if (!/^\d{4}$/.test(desde) || !/^\d{4}$/.test(hasta)) throw new Error('Escribe años válidos de cuatro dígitos.');
    inicio = `${desde}-01-01`; fin = `${hasta}-12-31`;
  }
  if (inicio > fin) throw new Error('La fecha inicial debe ser anterior o igual a la fecha final.');
  if (inicio < '2015-01-01') throw new Error('Elige un período a partir de 2015.');
  return { desde: inicio, hasta: fin };
}

// El backend informa el rango en días con decimales (hoy hasta ahora = 0.067). Se muestra en horas si
// dura menos de un día y en días enteros si no.
function duracionRango(dias: number): { cantidad: number; unidad: string } {
  if (dias < 1) {
    const horas = Math.max(1, Math.round(dias * 24));
    return { cantidad: horas, unidad: horas === 1 ? 'hora' : 'horas' };
  }
  const enteros = Math.round(dias);
  return { cantidad: enteros, unidad: enteros === 1 ? 'día' : 'días' };
}

// La última importación se recuerda en esta pestaña: al salir de Ingesta y volver, la tarjeta muestra
// su estado en lugar de «Sin confirmar». «Nueva importación» la olvida y deja el formulario vacío.
// Zonas de América Latina agrupadas por región y mostradas por su diferencia con UTC, como aparecen
// al buscar la hora de un país. Cada opción usa una zona IANA real de esa región: así las opciones de
// grupos distintos no se confunden y el horario de verano, donde existe, se aplica solo.
const ZONAS_LATAM: { region: string; zonas: [string, string][] }[] = [
  { region: 'Norteamérica (México)', zonas: [
    ['America/Cancun', 'UTC−05:00'], ['America/Mexico_City', 'UTC−06:00'],
    ['America/Hermosillo', 'UTC−07:00'], ['America/Tijuana', 'UTC−08:00 (UTC−07:00 en verano)'],
  ] },
  { region: 'Centroamérica y el Caribe', zonas: [
    ['America/Santo_Domingo', 'UTC−04:00'], ['America/Panama', 'UTC−05:00'], ['America/Guatemala', 'UTC−06:00'],
  ] },
  { region: 'Sudamérica', zonas: [
    ['America/Noronha', 'UTC−02:00'], ['America/Argentina/Buenos_Aires', 'UTC−03:00'],
    ['America/La_Paz', 'UTC−04:00'], ['America/Bogota', 'UTC−05:00'],
  ] },
];

const CLAVE_IMPORTACION = 'communitylab-discord-importacion';
type ImportacionGuardada = { id: string; unidad: Unidad; desde: string; hasta: string };
const FINALES_IMPORTACION = ['completada', 'completada_con_limite', 'cancelada', 'error'];

function leerImportacion(): ImportacionGuardada | null {
  try {
    const valor = JSON.parse(sessionStorage.getItem(CLAVE_IMPORTACION) ?? 'null');
    return valor && typeof valor.id === 'string' && ['dias', 'meses', 'anos'].includes(valor.unidad) ? valor : null;
  } catch { return null; }
}

function guardarImportacion(valor: ImportacionGuardada | null) {
  try {
    if (valor) sessionStorage.setItem(CLAVE_IMPORTACION, JSON.stringify(valor));
    else sessionStorage.removeItem(CLAVE_IMPORTACION);
  } catch { /* Sin almacenamiento la tarjeta funciona igual; solo no recuerda la importación. */ }
}

function DiscordIcon({ className = '' }: { className?: string }) {
  return <UiTree>{<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}><path d="M19.7 5.1a18 18 0 0 0-4.3-1.3l-.5 1a16 16 0 0 0-5.8 0l-.5-1a18 18 0 0 0-4.3 1.3C1.6 9.2.9 13.2 1.3 17.2a17 17 0 0 0 5.3 2.7l1.1-1.8-1.7-.8.4-.3a13 13 0 0 0 11.2 0l.4.3-1.7.8 1.1 1.8a17 17 0 0 0 5.3-2.7c.5-4.6-.8-8.5-3-12.1ZM8.5 14.9c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Zm7 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Z"/></svg>}</UiTree>;
}

export default function ConectarDiscord() {
  const [estados, setEstados] = useState<Record<number, EstadoEscuchaDiscord | null>>({});
  const [cambiando, setCambiando] = useState(false);
  const [errorControl, setErrorControl] = useState('');
  const conectados = useRef(new Map<number, string>());
  const alEstado = useCallback((indice: number, estado: EstadoEscuchaDiscord | null) => setEstados(actual => ({ ...actual, [indice]: estado })), []);
  const alConectar = useCallback((indice: number, canal: string) => { conectados.current.set(indice, canal); }, []);
  const duplicado = useCallback((indice: number, canal: string) => [...conectados.current.entries()].some(([otro, id]) => otro !== indice && id === canal), []);
  const conocidos = Object.entries(estados).filter((item): item is [string, EstadoEscuchaDiscord] => item[1] !== null);
  const escuchando = conocidos.some(([, estado]) => estado.escuchando);
  const conectado = conocidos.some(([, estado]) => estado.conectado);
  const etiqueta = cambiando ? 'Actualizando…' : conocidos.length === 0 ? 'Sin confirmar'
    : escuchando ? 'Escuchando' : conectado ? 'Conectado' : 'No autorizado';
  // Solo sirve para detener una importación en curso: encender sin importación no tiene efecto.
  const alternar = async () => {
    if (cambiando || !escuchando) return;
    setCambiando(true); setErrorControl('');
    await Promise.all(conocidos.map(async ([indice, estado]) => {
      try { alEstado(Number(indice), await cambiarEscuchaDiscord(estado.canal_id, !escuchando)); }
      catch { setErrorControl('No se pudo confirmar el cambio de escucha en todos los canales.'); }
    }));
    setCambiando(false);
  };
  return <UiTree>{<section className="card discord-connect" aria-labelledby="discord-connect-title">
    <div className="discord-panel-heading"><div className="discord-heading-copy"><span className="discord-brand-icon"><DiscordIcon className="h-5 w-5"/></span><div><h2 id="discord-connect-title">Conectar a Discord</h2><p>Importa los mensajes de un canal, con su período y zona horaria.</p></div></div>
      <button type="button" role="switch" aria-checked={escuchando} aria-label={escuchando ? 'Detener la importación del canal de Discord' : 'Estado del canal de Discord'} title={escuchando ? 'Pulsa para detener la importación' : undefined} disabled={cambiando || !escuchando} onClick={alternar} className={'discord-bot-control ' + (escuchando || conectado ? 'is-online' : '')}><DiscordIcon className="h-4 w-4"/><span className="discord-bot-dot"/><span>{etiqueta}</span></button>
    </div>
    {errorControl && <p role="alert" className="discord-message text-danger">{errorControl}</p>}
    <div className="discord-channel-list"><CanalDiscord indice={0} duplicado={duplicado} alConectar={alConectar} alEstado={alEstado} /></div>
  </section>}</UiTree>;
}

function CanalDiscord({ indice, alConectar, duplicado, alEstado }: { indice: number; alConectar: (indice: number, canal: string) => void; duplicado: (indice: number, canal: string) => boolean; alEstado: (indice: number, estado: EstadoEscuchaDiscord | null) => void }) {
  const [unidad, setUnidad] = useState<Unidad>('dias');
  const [canal, setCanal] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [zona, setZona] = useState('America/Guatemala');
  const [errorBot, setErrorBot] = useState('');
  const formRef = useRef<HTMLFormElement>(null);
  const ultimoIntento = useRef('');
  const apagados = useRef(new Set<string>());
  useEffect(() => {
    const controlador = new AbortController();
    const id = canal.trim();
    const timer = setTimeout(async () => {
      alEstado(indice, null); setErrorBot('');
      if (!/^[0-9]{17,20}$/.test(id)) return;
      try { const estado = await obtenerEscuchaDiscord(id, controlador.signal); if (!controlador.signal.aborted) alEstado(indice, estado); }
      catch { if (!controlador.signal.aborted) setErrorBot('Estado de escucha pendiente de confirmación.'); }
    }, 350);
    return () => { clearTimeout(timer); controlador.abort(); };
  }, [canal, indice, alEstado]);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [preview, setPreview] = useState<PrevisualizacionDiscord | null>(null);
  const [confirmado, setConfirmado] = useState(false);
  const [importacion, setImportacion] = useState<ImportacionDiscord | null>(null);
  const clave = useRef<string | null>(null);
  const enCurso = useRef(false);
  // Aviso inmediato: la conexión automática solo arranca con datos válidos, así que sin este aviso
  // un ID corto o un rango invertido no mostraban nada.
  const aviso = (() => {
    if (canal.trim() && !/^\d{17,20}$/.test(canal.trim())) return 'El ID del canal debe contener entre 17 y 20 dígitos.';
    if (!desde || !hasta) return '';
    try { rangoFechas(unidad, desde, hasta); return ''; } catch (err) { return (err as Error).message; }
  })();
  const invalidar = () => { setPreview(null); setImportacion(null); setConfirmado(false); setError(''); clave.current = null; };
  // Al volver a Ingesta se recupera la última importación de esta pestaña con su estado real.
  useEffect(() => {
    const guardada = leerImportacion();
    if (!guardada) return;
    let vigente = true;
    consultarImportacionDiscord(guardada.id).then(actual => {
      if (!vigente) return;
      // Ya terminada: la escucha se apagó en su momento y no se vuelve a pedir.
      if (FINALES_IMPORTACION.includes(actual.estado)) apagados.current.add(actual.id);
      setUnidad(guardada.unidad); setDesde(guardada.desde); setHasta(guardada.hasta);
      setZona(actual.zona); setCanal(actual.canal_id); setImportacion(actual);
      alConectar(indice, actual.canal_id);
    }).catch(err => {
      // Si ya no existe (p. ej. se eliminó su lote), se olvida; ante un fallo de red se conserva.
      if (vigente && (err as { response?: { status?: number } })?.response?.status === 404) guardarImportacion(null);
    });
    return () => { vigente = false; };
  }, [indice, alConectar]);
  const nuevaImportacion = () => {
    guardarImportacion(null);
    invalidar();
    ultimoIntento.current = '';
    setCanal(''); setDesde(''); setHasta('');
    alEstado(indice, null);
  };
  const conectar = async (event: React.FormEvent) => {
    event.preventDefault();
    if (enCurso.current) return;
    setError('');
    if (!/^\d{17,20}$/.test(canal.trim())) { setError('El ID del canal debe contener entre 17 y 20 dígitos.'); return; }
    if (duplicado(indice, canal.trim())) { setError('Este canal ya está configurado en otra conexión.'); return; }
    let fechas;
    try { fechas = rangoFechas(unidad, desde, hasta); } catch (err) { setError((err as Error).message); return; }
    enCurso.current = true; setOcupado(true);
    try {
      const vista = preview ?? await previsualizarDiscordHistorico({ canal_id: canal.trim(), ...fechas, zona, incluir_muestra: false });
      setPreview(vista);
      if (vista.limites.requiere_confirmacion && !confirmado) return;
      clave.current ??= crypto.randomUUID();
      const resultado = await crearImportacionDiscord({canal_id: canal.trim(), desde: vista.alcance_congelado.desde, hasta: vista.alcance_congelado.hasta, zona: vista.alcance_congelado.zona, confirmar_alcance: confirmado}, clave.current);
      setImportacion(resultado.importacion);
      guardarImportacion({ id: resultado.importacion.id, unidad, desde, hasta });
      alConectar(indice, canal.trim());
      // La importación ya existe: el interruptor pasa a «Escuchando» sin esperar al siguiente ciclo.
      obtenerEscuchaDiscord(canal.trim()).then(estado => alEstado(indice, estado)).catch(() => undefined);
    } catch (err) { const info = describirError(err); setError(`${info.titulo}. ${info.mensaje}`); }
    finally { setOcupado(false); enCurso.current = false; }
  };
  useEffect(() => {
    if (importacion || !/^[0-9]{17,20}$/.test(canal.trim()) || !desde || !hasta || !zona) return;
    try { rangoFechas(unidad, desde, hasta); } catch { return; }
    const intento = JSON.stringify([canal.trim(), unidad, desde, hasta, zona, confirmado]);
    if (ultimoIntento.current === intento) return;
    const timer = setTimeout(() => {
      if (!formRef.current?.checkValidity()) return;
      ultimoIntento.current = intento;
      formRef.current.requestSubmit();
    }, 1000);
    return () => clearTimeout(timer);
  }, [canal, unidad, desde, hasta, zona, confirmado, importacion]);
  useEffect(() => {
    if (!importacion || !['pendiente', 'ejecutando'].includes(importacion.estado)) return;
    let vigente = true;
    const timer = setTimeout(async () => {
      try {
        const actual = await consultarImportacionDiscord(importacion.id);
        if (vigente) setImportacion(actual);
        const estado = await obtenerEscuchaDiscord(importacion.canal_id);
        if (vigente) alEstado(indice, estado);
      }
      catch { if (vigente) setError('No se pudo actualizar el progreso de la importación.'); }
    }, 4000);
    return () => { vigente = false; clearTimeout(timer); };
  }, [importacion, indice, alEstado]);
  useEffect(() => {
    if (!importacion || ['pendiente', 'ejecutando'].includes(importacion.estado) || apagados.current.has(importacion.id)) return;
    apagados.current.add(importacion.id);
    let vigente = true;
    cambiarEscuchaDiscord(importacion.canal_id, false)
      .then(estado => { if (vigente) alEstado(indice, estado); })
      .catch(() => { if (vigente) setErrorBot('La carga terminó, pero no se pudo confirmar el apagado de la escucha.'); });
    return () => { vigente = false; };
  }, [importacion, indice, alEstado]);
  return <UiTree>{<div className="discord-channel-row" aria-labelledby={'discord-channel-title-' + indice}>
    <h3 id={'discord-channel-title-' + indice} className="text-sm font-bold mb-3">Canal</h3>
    {errorBot && <p className="discord-preview-note" role="status">{errorBot}</p>}
    <form ref={formRef} onSubmit={conectar} className="discord-connect-form">
      <fieldset disabled={ocupado || !!importacion} className="contents">
        <label className="discord-field"><span><Hash size={13}/> ID del canal de Discord</span><input className="input" inputMode="numeric" placeholder="Ej. 123456789012345678" value={canal} onChange={e=>{invalidar();alEstado(indice, null);setCanal(e.target.value);}} required pattern="[0-9]{17,20}"/><small>Activa el modo desarrollador en Discord y elige «Copiar ID del canal».</small></label>
        <div className="discord-date-heading"><span><CalendarDays size={14}/> Período de mensajes</span><div className="discord-date-tabs" role="group" aria-label="Seleccionar por días, meses o años">{([{id:'dias',nombre:'Días'},{id:'meses',nombre:'Meses'},{id:'anos',nombre:'Años'}] as const).map(item=><button key={item.id} type="button" aria-pressed={unidad===item.id} onClick={()=>{invalidar();setUnidad(item.id);setDesde('');setHasta('');}}>{item.nombre}</button>)}</div></div>
        <div className="discord-date-grid"><label className="discord-field"><span>Desde</span><input aria-label="Inicio del período" className="input" type={unidad==='dias'?'date':unidad==='meses'?'month':'number'} min={unidad==='anos'?'2015':unidad==='meses'?'2015-01':'2015-01-01'} max={unidad==='anos'?'9999':undefined} placeholder={unidad==='anos'?'2025':undefined} required value={desde} onChange={e=>{invalidar();setDesde(e.target.value);}}/></label><span className="discord-range-arrow"><ArrowRight size={15}/></span><label className="discord-field"><span>Hasta</span><input aria-label="Final del período" className="input" type={unidad==='dias'?'date':unidad==='meses'?'month':'number'} min={desde || (unidad==='anos'?'2015':undefined)} max={unidad==='anos'?'9999':undefined} placeholder={unidad==='anos'?'2026':undefined} required value={hasta} onChange={e=>{invalidar();setHasta(e.target.value);}}/></label></div>
        <label className="discord-field"><span>Zona horaria</span><span className="discord-timezone-control"><select className="input" value={zona} onChange={e=>{invalidar();setZona(e.target.value);}}>{!ZONAS_LATAM.some(g => g.zonas.some(([valor]) => valor === zona)) && <option value={zona}>{zona}</option>}{ZONAS_LATAM.map(g => <optgroup key={g.region} label={g.region}>{g.zonas.map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</optgroup>)}</select><ChevronDown size={16} aria-hidden="true" /></span></label>
      </fieldset>
      {preview?.limites.requiere_confirmacion && !importacion && <label className="discord-confirm"><input type="checkbox" checked={confirmado} onChange={e=>setConfirmado(e.target.checked)} disabled={ocupado}/>Confirmo la importación de este rango de {duracionRango(preview.rango.dias).cantidad} {duracionRango(preview.rango.dias).unidad}, con un máximo de {preview.limites.max_mensajes} mensajes.</label>}
      {error && <p className="discord-message text-danger" role="alert"><AlertCircle size={16}/>{error}</p>}
      {!error && aviso && <p className="discord-message text-danger" role="alert"><AlertCircle size={16}/>{aviso}</p>}
      {importacion && <div className="discord-message text-success" role="status"><CheckCircle2 size={16}/><div>Solicitud recibida: {importacion.estado}.<p className="text-xs text-muted-foreground mt-1 break-all">Importación {importacion.id}</p></div></div>}
      {importacion && ['completada', 'completada_con_limite', 'cancelada'].includes(importacion.estado) && <EnviarAnalisisDiscord importacionId={importacion.id}/>}
      <div className="discord-connect-footer"><p className="discord-auto-connect-note"><AlertCircle size={16} aria-hidden="true"/><span>{ocupado ? 'Conectando…' : importacion ? 'La escucha se apaga al finalizar la carga.' : 'La conexión comienza al completar el ID, las fechas y la zona horaria.'}</span></p>{importacion && FINALES_IMPORTACION.includes(importacion.estado) && <button type="button" className="btn-secondary" onClick={nuevaImportacion}>Nueva importación</button>}{(error || preview?.limites.requiere_confirmacion) && !importacion && <button className="btn-primary" type="submit" disabled={ocupado || !!importacion || (!!preview?.limites.requiere_confirmacion && !confirmado)}>{ocupado?<Loader2 size={14} className="animate-spin"/>:<DiscordIcon className="h-4 w-4"/>}{ocupado?'Conectando…':importacion?'Solicitud enviada':preview?.limites.requiere_confirmacion?'Confirmar y conectar':'Reintentar'}</button>}</div>
    </form>
  </div>}</UiTree>;
}
