'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import UiTree from '@/components/UiTree';
import { AlertCircle, ArrowUpRight, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { describirError, enviarImportacionAAnalisis, obtenerResumenAnalisisDiscord, type ResumenAnalisisDiscord } from '@/services/api';

// Paso posterior a importar: los mensajes importados quedan guardados aparte hasta que una persona
// operadora decide enviarlos al análisis con IA (una llamada a Gemini por bloque de mensajes).
export default function EnviarAnalisisDiscord({ importacionId }: { importacionId: string }) {
  const [resumen, setResumen] = useState<ResumenAnalisisDiscord | null>(null);
  const [enviado, setEnviado] = useState<ResumenAnalisisDiscord | null>(null);
  const [confirmado, setConfirmado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState('');
  const enCurso = useRef(false);

  useEffect(() => {
    let vigente = true;
    obtenerResumenAnalisisDiscord(importacionId)
      .then((r) => { if (vigente) { setResumen(r); setEnviado(null); setConfirmado(false); setError(''); } })
      .catch((err) => { if (vigente) { const info = describirError(err); setError(`${info.titulo}. ${info.mensaje}`); } });
    return () => { vigente = false; };
  }, [importacionId]);

  const enviar = async () => {
    if (enCurso.current) return;
    enCurso.current = true; setOcupado(true); setError('');
    try {
      const r = await enviarImportacionAAnalisis(importacionId);
      setEnviado(r);
      setResumen(await obtenerResumenAnalisisDiscord(importacionId));
    } catch (err) { const info = describirError(err); setError(`${info.titulo}. ${info.mensaje}`); }
    finally { setOcupado(false); enCurso.current = false; }
  };

  if (!resumen) {
    return error
      ? <p className="discord-message text-danger" role="alert"><AlertCircle size={16}/>{error}</p>
      : <p className="text-xs text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin"/>Revisando qué falta enviar al análisis…</p>;
  }
  const trabajos = enviado?.trabajos ?? [];
  return <UiTree>{<div className="discord-analysis rounded-xl border border-border p-4 space-y-3 text-sm">
    <div className="flex items-center gap-2 font-semibold text-foreground"><Sparkles size={15}/>Análisis con IA</div>
    <p className="text-muted-foreground text-xs">
      {resumen.total} importados · {resumen.ya_en_analisis} ya están en el análisis · {resumen.sin_contenido} sin texto · <strong className="text-foreground">{resumen.pendientes} por enviar</strong>
      {resumen.pendientes > 0 && <> en {resumen.lotes} {resumen.lotes === 1 ? 'lote' : 'lotes'} ({resumen.semanas.join(', ')})</>}.
    </p>
    {trabajos.length > 0 && <div className="discord-message text-success" role="status"><CheckCircle2 size={16}/><div>
      {trabajos.reduce((n, t) => n + t.mensajes, 0)} mensajes enviados en {trabajos.length} {trabajos.length === 1 ? 'lote' : 'lotes'}. El análisis corre en segundo plano.
      <p className="mt-1"><Link href="/interacciones" className="inline-flex items-center gap-1 underline">Ver en Interacciones <ArrowUpRight size={13}/></Link></p>
    </div></div>}
    {resumen.pendientes > 0 && resumen.importacion_finalizada && <>
      <label className="discord-confirm"><input type="checkbox" checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} disabled={ocupado}/>Entiendo que se usará la IA (Gemini) para analizar {resumen.pendientes} mensajes y generar borradores por semana.</label>
      <button type="button" className="btn-primary" onClick={enviar} disabled={!confirmado || ocupado}>
        {ocupado ? <Loader2 size={14} className="animate-spin"/> : <Sparkles size={14}/>}{ocupado ? 'Enviando…' : 'Enviar al análisis'}
      </button>
    </>}
    {resumen.pendientes === 0 && trabajos.length === 0 && <p className="text-xs text-muted-foreground">No hay mensajes nuevos para analizar en esta importación.</p>}
    {error && <p className="discord-message text-danger" role="alert"><AlertCircle size={16}/>{error}</p>}
  </div>}</UiTree>;
}
