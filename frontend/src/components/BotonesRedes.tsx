'use client';

import UiTree from '@/components/UiTree';
import { useState } from 'react';

// Abren la red con el texto generado ya escrito; la persona revisa y publica allí (nada se publica solo).
// X admite el texto en el enlace de publicación. LinkedIn solo admite oficialmente compartir una URL:
// se intenta prellenar el texto y, además, se copia al portapapeles para pegarlo si no aparece.
const LINKEDIN = 'https://www.linkedin.com/feed/?shareActive=true&text=';
const X = 'https://x.com/intent/post?text=';
const MAX_X = 280;

// Sin versión para X se usa la de LinkedIn, recortada al máximo de X.
function paraX(textoX: string, textoLinkedin: string) {
  const texto = (textoX.trim() || textoLinkedin.trim());
  return texto.length <= MAX_X ? texto : texto.slice(0, MAX_X - 1).trimEnd() + '…';
}

function LogoLinkedin() {
  return <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#0A66C2" aria-hidden="true"><path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12ZM7.12 20.45H3.56V9h3.56v11.45ZM22.23 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.46c.98 0 1.77-.77 1.77-1.73V1.73C24 .77 23.21 0 22.23 0Z"/></svg>;
}

function LogoX() {
  return <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.65l-5.21-6.82-5.97 6.82H1.68l7.73-8.84L1.25 2.25h6.83l4.71 6.23 5.45-6.23Zm-1.16 17.52h1.83L7.08 4.13H5.12l11.96 15.64Z"/></svg>;
}

export default function BotonesRedes({ textoLinkedin = '', textoX = '' }: { textoLinkedin?: string; textoX?: string }) {
  const [aviso, setAviso] = useState('');
  const linkedin = textoLinkedin.trim();
  const x = paraX(textoX, textoLinkedin);
  const copiar = () => {
    if (!linkedin) return;
    navigator.clipboard?.writeText(linkedin)
      .then(() => setAviso('Texto de LinkedIn copiado: si no aparece en la publicación, pégalo con Ctrl + V.'))
      .catch(() => setAviso(''));
  };
  return <UiTree>{<div className="mb-4">
    <div className="flex flex-wrap gap-2">
      <a className="btn-red btn-red-linkedin" href={linkedin ? LINKEDIN + encodeURIComponent(linkedin) : 'https://www.linkedin.com/'}
        target="_blank" rel="noopener noreferrer" onClick={copiar}
        title={linkedin ? 'Abre LinkedIn con el texto para publicar (no se publica solo)' : 'Abrir LinkedIn'}>
        <LogoLinkedin />LinkedIn
      </a>
      <a className="btn-red btn-red-x" href={x ? X + encodeURIComponent(x) : 'https://x.com/'} target="_blank" rel="noopener noreferrer"
        title={x ? 'Abre X con el texto para publicar (no se publica solo)' : 'Abrir X'}>
        <LogoX />X
      </a>
    </div>
    {aviso && <p role="status" className="text-xs text-muted-foreground mt-2">{aviso}</p>}
  </div>}</UiTree>;
}
