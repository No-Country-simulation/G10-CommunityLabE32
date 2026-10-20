'use client';

import { useRef, useState } from 'react';
import { CalendarDays, Hash, Loader2, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { previsualizarDiscordHistorico, crearImportacionDiscord, describirError, type PrevisualizacionDiscord, type ImportacionDiscord } from '@/services/api';

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

function DiscordIcon({ className = '' }: { className?: string }) {
  return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}><path d="M19.7 5.1a18 18 0 0 0-4.3-1.3l-.5 1a16 16 0 0 0-5.8 0l-.5-1a18 18 0 0 0-4.3 1.3C1.6 9.2.9 13.2 1.3 17.2a17 17 0 0 0 5.3 2.7l1.1-1.8-1.7-.8.4-.3a13 13 0 0 0 11.2 0l.4.3-1.7.8 1.1 1.8a17 17 0 0 0 5.3-2.7c.5-4.6-.8-8.5-3-12.1ZM8.5 14.9c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Zm7 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Z"/></svg>;
}

export default function ConectarDiscord() {
  const [unidad, setUnidad] = useState<Unidad>('dias');
  const [canal, setCanal] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [zona, setZona] = useState('America/Guatemala');
  const [escucha, setEscucha] = useState(false);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [preview, setPreview] = useState<PrevisualizacionDiscord | null>(null);
  const [confirmado, setConfirmado] = useState(false);
  const [importacion, setImportacion] = useState<ImportacionDiscord | null>(null);
  const clave = useRef<string | null>(null);
  const enCurso = useRef(false);
  const invalidar = () => { setPreview(null); setImportacion(null); setConfirmado(false); setError(''); clave.current = null; };
  let rango: { desde: string; hasta: string } | null = null;
  try { rango = rangoFechas(unidad, desde, hasta); } catch {}
  const conectar = async (event: React.FormEvent) => {
    event.preventDefault();
    if (enCurso.current) return;
    setError('');
    if (!/^\d{17,20}$/.test(canal.trim())) { setError('El ID del canal debe contener entre 17 y 20 dígitos.'); return; }
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
    } catch (err) { const info = describirError(err); setError(`${info.titulo}. ${info.mensaje}`); }
    finally { setOcupado(false); enCurso.current = false; }
  };
  return <section className="card discord-connect" aria-labelledby="discord-connect-title">
    <div className="discord-panel-heading"><div className="discord-heading-copy"><span className="discord-brand-icon"><DiscordIcon className="h-5 w-5"/></span><div><h2 id="discord-connect-title">Conectar a Discord</h2><p>Elige un canal y trae únicamente los mensajes del período que necesitas.</p></div></div><button type="button" role="switch" aria-checked={escucha} aria-label="Vista previa de escucha del bot" onClick={()=>setEscucha(!escucha)} className={`discord-bot-control ${escucha ? 'is-online' : ''}`} title="Vista previa del estado del bot"><DiscordIcon className="h-4 w-4"/><span className="discord-bot-dot"/><span>{escucha ? 'En línea' : 'Apagado'}</span></button></div>
    <p className="discord-preview-note">Control del bot en vista previa: no modifica el bot real.</p>
    <form onSubmit={conectar} className="discord-connect-form">
      <fieldset disabled={ocupado} className="contents">
        <label className="discord-field"><span><Hash size={13}/> ID del canal de Discord</span><input className="input" inputMode="numeric" placeholder="Ej. 123456789012345678" value={canal} onChange={e=>{invalidar();setCanal(e.target.value);}} required pattern="[0-9]{17,20}"/><small>Activa el modo desarrollador en Discord y elige «Copiar ID del canal».</small></label>
        <div className="discord-date-heading"><span><CalendarDays size={14}/> Período de mensajes</span><div className="discord-date-tabs" role="group" aria-label="Seleccionar por días, meses o años">{([{id:'dias',nombre:'Días'},{id:'meses',nombre:'Meses'},{id:'anos',nombre:'Años'}] as const).map(item=><button key={item.id} type="button" aria-pressed={unidad===item.id} onClick={()=>{invalidar();setUnidad(item.id);setDesde('');setHasta('');}}>{item.nombre}</button>)}</div></div>
        <div className="discord-date-grid"><label className="discord-field"><span>Desde</span><input aria-label="Inicio del período" className="input" type={unidad==='dias'?'date':unidad==='meses'?'month':'number'} min={unidad==='anos'?'2015':unidad==='meses'?'2015-01':'2015-01-01'} max={unidad==='anos'?'9999':undefined} placeholder={unidad==='anos'?'2025':undefined} required value={desde} onChange={e=>{invalidar();setDesde(e.target.value);}}/></label><span className="discord-range-arrow"><ArrowRight size={15}/></span><label className="discord-field"><span>Hasta</span><input aria-label="Final del período" className="input" type={unidad==='dias'?'date':unidad==='meses'?'month':'number'} min={desde || (unidad==='anos'?'2015':undefined)} max={unidad==='anos'?'9999':undefined} placeholder={unidad==='anos'?'2026':undefined} required value={hasta} onChange={e=>{invalidar();setHasta(e.target.value);}}/></label></div>
        <label className="discord-field"><span>Zona horaria</span><select className="input" value={zona} onChange={e=>{invalidar();setZona(e.target.value);}}><option value="America/Guatemala">Guatemala · UTC−06:00</option><option value="America/Mexico_City">Ciudad de México</option><option value="America/Bogota">Bogotá / Lima · UTC−05:00</option><option value="America/Argentina/Buenos_Aires">Buenos Aires · UTC−03:00</option><option value="Europe/Madrid">Madrid</option><option value="UTC">UTC</option></select></label>
      </fieldset>
      <div className="discord-range-summary"><CalendarDays size={15}/><p>{rango ? <>Se solicitarán los mensajes del <strong>{rango.desde}</strong> al <strong>{rango.hasta}</strong>, ambos días incluidos.</> : 'Selecciona un rango para definir qué mensajes se enviarán a la importación.'}</p></div>
      {preview?.limites.requiere_confirmacion && !importacion && <label className="discord-confirm"><input type="checkbox" checked={confirmado} onChange={e=>setConfirmado(e.target.checked)} disabled={ocupado}/>Confirmo la importación de este rango de {preview.rango.dias} días, con un máximo de {preview.limites.max_mensajes} mensajes.</label>}
      {error && <p className="discord-message text-danger" role="alert"><AlertCircle size={16}/>{error}</p>}
      {importacion && <div className="discord-message text-success" role="status"><CheckCircle2 size={16}/><div>Solicitud recibida: {importacion.estado}.<p className="text-xs text-muted-foreground mt-1 break-all">Importación {importacion.id}</p></div></div>}
      <div className="discord-connect-footer"><p>Solo se importará el historial del rango elegido. No activa la escucha en tiempo real.</p><button className="btn-primary" type="submit" disabled={ocupado || !!importacion || (!!preview?.limites.requiere_confirmacion && !confirmado)}>{ocupado?<Loader2 size={14} className="animate-spin"/>:<DiscordIcon className="h-4 w-4"/>}{ocupado?'Conectando…':importacion?'Solicitud enviada':preview?.limites.requiere_confirmacion?'Confirmar y conectar':'Conectar'}</button></div>
    </form>
  </section>;
}
