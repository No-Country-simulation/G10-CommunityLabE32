'use client';
import { useId, useRef } from 'react';
import { X } from 'lucide-react';
import UiTree from '@/components/UiTree';
export default function VerMensaje({ texto, autor, canal, idMensaje }: { texto: string; autor: string; canal: string; idMensaje: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titulo = useId();
  return <UiTree>{<><button type="button" className="btn-secondary mt-3" onClick={() => dialog.current?.showModal()}>Ver mensaje</button><dialog ref={dialog} className="message-detail-dialog" aria-labelledby={titulo} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close(); }}><div className="flex items-center justify-between gap-4"><h2 id={titulo} className="text-lg font-bold">Mensaje original</h2><button type="button" className="btn-ghost" aria-label="Cerrar mensaje" onClick={() => dialog.current?.close()}><X size={20}/></button></div><p className="mt-4 text-sm" translate="no">{/^\d{16,22}$/.test(autor) ? 'Integrante de Discord' : autor} · {canal}</p><p className="mt-5 whitespace-pre-wrap break-words" translate="no">{texto}</p><details className="mt-5 text-xs text-muted-foreground"><summary>Identificador del mensaje</summary><code translate="no" className="break-all">{idMensaje}</code></details></dialog></>}</UiTree>;
}
