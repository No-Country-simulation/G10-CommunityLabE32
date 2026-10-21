'use client';

import UiTree from '@/components/UiTree';
import React from 'react';
interface TokenOperadorProps { className?: string; }
export default function TokenOperador({className=''}:TokenOperadorProps) {
  return <UiTree>{<p className={`text-xs text-muted-foreground flex items-center gap-2 ${className}`}><span className="w-2 h-2 rounded-full bg-current opacity-50 inline-block"/>Las acciones de operador requieren una sesión autorizada por el servidor.</p>}</UiTree>;
}
