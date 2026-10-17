'use client';

import { useState, useSyncExternalStore } from 'react';
import { KeyRound, LockOpen, X } from 'lucide-react';
import { EVENTO_OPERADOR, guardarTokenOperador, leerTokenOperador } from '@/services/api';

const subscribe = (cb: () => void) => {
  window.addEventListener(EVENTO_OPERADOR, cb);
  return () => window.removeEventListener(EVENTO_OPERADOR, cb);
};
const getSnapshot = () => leerTokenOperador() !== '';
const getServerSnapshot = () => false;

export const useTokenOperador = () => useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

// Token de operador para acciones protegidas. Se guarda solo en esta pestaña y nunca se muestra.
export default function TokenOperador({ className = '' }: { className?: string }) {
  const configurado = useTokenOperador();
  const [valor, setValor] = useState('');

  if (configurado) {
    return (
      <p className={`flex items-center gap-2 text-xs text-muted-foreground ${className}`}>
        <LockOpen className="w-3.5 h-3.5 text-success shrink-0" />
        Token de operador activo en esta pestaña
        <button onClick={() => guardarTokenOperador('')} className="btn-ghost px-2! py-1! ml-auto">
          <X className="w-3.5 h-3.5" /> Quitar
        </button>
      </p>
    );
  }
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (valor.trim()) { guardarTokenOperador(valor.trim()); setValor(''); } }}
      className={`flex items-center gap-2 ${className}`}
    >
      <KeyRound className="w-4 h-4 text-subtle-foreground shrink-0" />
      <input
        type="password"
        autoComplete="off"
        className="input py-1.5! text-sm"
        placeholder="Token de operador"
        aria-label="Token de operador"
        value={valor}
        maxLength={256}
        onChange={(e) => setValor(e.target.value)}
      />
      <button type="submit" disabled={!valor.trim()} className="btn-secondary px-3! py-1.5! shrink-0">
        Usar
      </button>
    </form>
  );
}
